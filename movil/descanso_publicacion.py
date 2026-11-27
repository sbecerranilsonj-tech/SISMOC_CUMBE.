"""Publicación preventiva de asignaciones; no valida el reporte ni el pago."""
from datetime import datetime, timedelta
from bisect import bisect_right
from collections import defaultdict

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import AutorizacionInicialDescanso, Descanso, Operacion, Perfil, ReglaDescanso


def sin_viaje_reciente(anterior, salida):
    """Sin viaje el día anterior (ni el mismo día) se considera descansado.

    Un itinerario histórico sin llegada real no debe impedir un viaje
    posterior cuando el conductor no trabajó ni el día anterior ni el día
    del viaje; la revisión de descanso sigue siendo obligatoria en caso
    contrario.
    """
    return anterior is None or anterior.salida.fecha < salida.fecha - timedelta(days=1)


def evaluar_descanso(operacion, perfil, momento=None):
    if not getattr(settings, 'SISMOC_DESCANSO_PUBLICACION_HABILITADA', False):
        return True, ''
    regla = ReglaDescanso.objects.first()
    if not regla or not regla.activa:
        return True, ''
    if not perfil or not perfil.activo or not perfil.usuario.is_active:
        return False, 'El conductor no tiene una cuenta activa.'

    salida = operacion.salida
    inicio = momento or timezone.make_aware(
        datetime.combine(salida.fecha, salida.hora),
        timezone.get_default_timezone(),
    )
    alta = AutorizacionInicialDescanso.objects.filter(
        perfil=perfil, autorizado_el__lte=inicio,
    ).first()
    anteriores = Operacion.objects.filter(
        salida__importacion__estado='VALIDADO', salida__anulado=False,
    ).exclude(estado='CANCELADO').exclude(
        salida__estado_operativo='CANCELADO'
    ).exclude(pk=operacion.pk).filter(
        Q(salida__conductor_uno_id=perfil.conductor_id)
        | Q(salida__conductor_dos_id=perfil.conductor_id)
    ).filter(
        Q(salida__fecha__lt=salida.fecha)
        | Q(salida__fecha=salida.fecha, salida__hora__lte=salida.hora)
    ).select_related('salida').order_by('-salida__fecha', '-salida__hora', '-pk')
    if alta:
        # La autorización inicial fija un punto de partida auditado: no se
        # exige reconstruir descansos de itinerarios históricos anteriores.
        anteriores = anteriores.filter(
            Q(salida__fecha__gt=timezone.localtime(alta.autorizado_el).date())
            | Q(salida__fecha=timezone.localtime(alta.autorizado_el).date(),
                salida__hora__gte=timezone.localtime(alta.autorizado_el).time())
        )
    anterior = anteriores.first()
    if sin_viaje_reciente(anterior, salida):
        return True, ''

    if anterior.llegada_real is None:
        return False, 'Sin llegada real registrada en el viaje anterior; no se puede confirmar el descanso de 8 horas.'
    # El descanso se calcula automáticamente desde la llegada real registrada:
    # no requiere que Control firme ni que se abra un registro de descanso.
    habilitado = anterior.llegada_real + timedelta(hours=regla.horas)
    if inicio < habilitado:
        return False, (f'Descanso insuficiente: disponible desde '
                       f'{timezone.localtime(habilitado):%d/%m %H:%M}.')
    return True, ''


def disponibilidad_conductor(perfil, momento):
    """Devuelve (disponible, motivo, desde) para un conductor en un momento."""
    if not perfil or not perfil.activo or not perfil.usuario.is_active:
        return False, 'Cuenta móvil no activa.', ''
    regla = ReglaDescanso.objects.first()
    horas = regla.horas if regla and regla.activa else 8
    anterior = Operacion.objects.filter(
        salida__importacion__estado='VALIDADO', salida__anulado=False,
    ).exclude(estado='CANCELADO').exclude(
        salida__estado_operativo='CANCELADO'
    ).filter(
        Q(salida__conductor_uno_id=perfil.conductor_id)
        | Q(salida__conductor_dos_id=perfil.conductor_id)
    ).filter(
        Q(salida__fecha__lt=momento.date())
        | Q(salida__fecha=momento.date(),
            salida__hora__lte=momento.time())
    ).select_related('salida').order_by(
        '-salida__fecha', '-salida__hora', '-pk').first()
    if anterior is None or anterior.salida.fecha < momento.date() - timedelta(days=1):
        return True, 'Sin viaje previo en las últimas 24 horas.', ''
    if anterior.llegada_real is None:
        return False, 'Sin llegada real registrada en el viaje anterior.', ''
    desde = anterior.llegada_real + timedelta(hours=horas)
    if momento < desde:
        return False, 'Aún no cumple las 8 horas de descanso.', desde
    return True, 'Disponible.', desde


def estado_publicacion(operacion):
    """Ambos conductores deben estar habilitados antes de ver la asignación."""
    if (operacion.salida.importacion.estado != 'VALIDADO'
            or operacion.salida.anulado
            or operacion.salida.estado_operativo == 'CANCELADO'
            or operacion.estado == 'CANCELADO'):
        return False, 'Reporte sin validar o salida anulada/cancelada.'
    if operacion.estado != 'PROGRAMADO':
        return True, ''
    if operacion.salida.original.get('origen_programacion') == 'MANUAL':
        from .programacion_manual import firma_asignacion
        if (not operacion.salida.original.get('publicacion_descanso_autorizada')
                or operacion.salida.original.get('firma_asignacion_publicada')
                != firma_asignacion(operacion.salida)):
            from .programacion_manual import comprobar_descanso
            permitido, motivo_descanso = comprobar_descanso(operacion)
            return False, (f'Programación manual pendiente: '
                           f'{motivo_descanso or "descanso por comprobar"}')
    perfiles = {
        p.conductor_id: p for p in Perfil.objects.filter(
            conductor_id__in=[
                operacion.salida.conductor_uno_id,
                operacion.salida.conductor_dos_id,
            ], activo=True,
        ).select_related('usuario')
    }
    razones = []
    for conductor in (operacion.salida.conductor_uno, operacion.salida.conductor_dos):
        if conductor is None:
            razones.append('Falta identificar a un conductor.')
            continue
        permitido, motivo = evaluar_descanso(
            operacion, perfiles.get(conductor.pk),
        )
        if not permitido:
            razones.append(f'{conductor.nombre_apellidos}: {motivo}')
    return not razones, ' '.join(razones)


class EvaluadorPublicacionLote:
    """Mismo control preventivo para un calendario entero, sin consultas por celda."""

    def __init__(self, operaciones, regla):
        self.regla = regla
        ids = {
            cid for op in operaciones
            for cid in (op.salida.conductor_uno_id, op.salida.conductor_dos_id)
            if cid is not None
        }
        self.perfiles = {
            p.conductor_id: p for p in Perfil.objects.filter(
                conductor_id__in=ids, activo=True,
            ).select_related('usuario')
        }
        perfiles_ids = [p.pk for p in self.perfiles.values()]
        self.altas = {
            a.perfil_id: a.autorizado_el for a in
            AutorizacionInicialDescanso.objects.filter(perfil_id__in=perfiles_ids)
        }
        self.historial = defaultdict(list)
        if ids:
            anteriores = Operacion.objects.filter(
                salida__importacion__estado='VALIDADO', salida__anulado=False,
            ).exclude(estado='CANCELADO').exclude(
                salida__estado_operativo='CANCELADO'
            ).filter(
                Q(salida__conductor_uno_id__in=ids)
                | Q(salida__conductor_dos_id__in=ids)
            ).select_related('salida').order_by(
                'salida__fecha', 'salida__hora', 'pk',
            )
            for anterior in anteriores:
                for cid in {anterior.salida.conductor_uno_id,
                            anterior.salida.conductor_dos_id} & ids:
                    self.historial[cid].append(anterior)
        self.claves = {
            cid: [(op.salida.fecha, op.salida.hora, op.pk) for op in ops]
            for cid, ops in self.historial.items()
        }
        self.descansos = defaultdict(list)
        for descanso in Descanso.objects.filter(
            perfil_id__in=perfiles_ids,
        ).order_by('inicio', 'pk'):
            self.descansos[descanso.perfil_id].append(descanso)
        self.inicios = {
            pid: [d.inicio for d in descansos]
            for pid, descansos in self.descansos.items()
        }

    def evaluar(self, operacion, perfil):
        if not perfil or not perfil.usuario.is_active:
            return False, 'El conductor no tiene una cuenta activa.'
        salida = operacion.salida
        inicio = timezone.make_aware(
            datetime.combine(salida.fecha, salida.hora),
            timezone.get_default_timezone(),
        )
        alta = self.altas.get(perfil.pk)
        if alta is not None and alta > inicio:
            alta = None
        cid = perfil.conductor_id
        claves = self.claves.get(cid, [])
        # El evaluador individual excluye la operación actual y permite
        # otras salidas de la misma hora, incluso con identificador mayor.
        pos = bisect_right(claves, (salida.fecha, salida.hora, float('inf')))
        anteriores = self.historial.get(cid, [])
        anterior = None
        for candidato in reversed(anteriores[:pos]):
            if candidato.pk == operacion.pk:
                continue
            if alta and timezone.make_aware(
                datetime.combine(candidato.salida.fecha, candidato.salida.hora),
                timezone.get_default_timezone(),
            ) < alta:
                break
            anterior = candidato
            break
        if sin_viaje_reciente(anterior, salida):
            return True, ''
        if anterior.llegada_real is None:
            return False, 'Sin llegada real registrada en el viaje anterior; no se puede confirmar el descanso de 8 horas.'
        habilitado = anterior.llegada_real + timedelta(hours=self.regla.horas)
        if inicio < habilitado:
            return False, (f'Descanso insuficiente: disponible desde '
                           f'{timezone.localtime(habilitado):%d/%m %H:%M}.')
        return True, ''

    def estado(self, operacion):
        salida = operacion.salida
        if (salida.importacion.estado != 'VALIDADO' or salida.anulado
                or salida.estado_operativo == 'CANCELADO'
                or operacion.estado == 'CANCELADO'):
            return False, 'Reporte sin validar o salida anulada/cancelada.'
        if operacion.estado != 'PROGRAMADO':
            return True, ''
        if salida.original.get('origen_programacion') == 'MANUAL':
            from .programacion_manual import comprobar_descanso, firma_asignacion
            if (not salida.original.get('publicacion_descanso_autorizada')
                    or salida.original.get('firma_asignacion_publicada')
                    != firma_asignacion(salida)):
                permitido, motivo_descanso = comprobar_descanso(operacion)
                return False, (f'Programación manual pendiente: '
                               f'{motivo_descanso or "descanso por comprobar"}')
        razones = []
        for conductor in (salida.conductor_uno, salida.conductor_dos):
            if conductor is None:
                razones.append('Falta identificar a un conductor.')
                continue
            permitido, motivo = self.evaluar(
                operacion, self.perfiles.get(conductor.pk),
            )
            if not permitido:
                razones.append(f'{conductor.nombre_apellidos}: {motivo}')
        return not razones, ' '.join(razones)
