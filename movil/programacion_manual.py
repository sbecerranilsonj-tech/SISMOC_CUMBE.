"""Programaciones creadas en Buses y Flota sin alterar el Excel original."""
import hashlib
import re
import uuid
from datetime import date, time

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from conductores.models import Conductor, Importacion, Salida
from conductores.parser import normalizar
from asistencia.models import Trabajador
from .models import Auditoria, Operacion, Perfil
from .views import Problema, exigir


def sede(valor):
    texto = str(valor or '').strip().lower()
    for separador in ('·', '|', '/'):
        texto = texto.split(separador)[-1].strip()
    texto = re.sub(r'\s*[–—-]\s*', ' ', texto)
    return normalizar(texto)


def firma_asignacion(salida):
    """Una aprobación de descanso solo vale para esta pareja y salida exacta."""
    return [
        str(salida.fecha), salida.hora.isoformat(), salida.bus,
        salida.origen, salida.destino,
        salida.conductor_uno_id, salida.conductor_dos_id,
    ]


def placas_disponibles():
    """La fuente de placas son salidas validadas, no un catálogo inventado."""
    return list(Salida.objects.filter(
        importacion__estado='VALIDADO', anulado=False,
    ).exclude(estado_operativo='CANCELADO').exclude(
        bus=''
    ).order_by('bus').values_list('bus', flat=True).distinct())


def sedes_disponibles():
    """Sedes registradas y puntos de ruta de itinerarios validados."""
    salidas = Salida.objects.filter(importacion__estado='VALIDADO', anulado=False)
    valores = {sede(t) for t in Trabajador.objects.exclude(sede='').values_list('sede', flat=True)}
    valores.update(sede(s) for s in salidas.exclude(origen='').values_list('origen', flat=True))
    valores.update(sede(s) for s in salidas.exclude(destino='').values_list('destino', flat=True))
    return sorted((s for s in valores if s), key=normalizar)


def referencia_registrada(valor, opciones):
    return next((opcion for opcion in opciones if normalizar(opcion) == normalizar(valor)), None)


@transaction.atomic
def programar(datos, usuario):
    try:
        fecha = date.fromisoformat(datos.get('fecha', ''))
        hora = time.fromisoformat(datos.get('hora', ''))
        c1 = int(datos.get('conductor_uno', ''))
        c2 = int(datos.get('conductor_dos', ''))
    except (TypeError, ValueError) as exc:
        raise Problema('Complete fecha, hora y ambos conductores registrados.') from exc
    exigir(fecha >= timezone.localdate(), 'La programación histórica es solo lectura.')
    exigir(c1 != c2, 'Seleccione dos conductores distintos.')
    conductores = {c.pk: c for c in Conductor.objects.filter(pk__in=(c1, c2))}
    exigir(len(conductores) == 2, 'Seleccione conductores de las fichas existentes.')
    bus = referencia_registrada(str(datos.get('bus', '')).strip(), placas_disponibles())
    exigir(bus, 'Seleccione una placa de itinerarios validados.')
    sedes = sedes_disponibles()
    valor_origen = str(datos.get('origen', '')).strip()
    valor_destino = str(datos.get('destino', '')).strip()
    origen = referencia_registrada(valor_origen, sedes) or valor_origen
    destino = referencia_registrada(valor_destino, sedes) or valor_destino
    exigir(origen and destino and normalizar(sede(origen)) != normalizar(sede(destino)),
           'Seleccione sedes registradas distintas para origen y destino.')
    clave = hashlib.sha256('|'.join((
        fecha.isoformat(), hora.isoformat(), normalizar(bus),
        normalizar(origen), normalizar(destino),
    )).encode()).hexdigest()
    # Un registro importado o manual nunca se sobreescribe por crear otra salida.
    exigir(not Salida.objects.filter(clave_confirmada=clave).exists(),
           'La salida ya está programada. Revise la ficha existente.', 409)
    ocupadas = Salida.objects.filter(fecha=fecha, anulado=False).exclude(
        estado_operativo='CANCELADO')
    exigir(not ocupadas.filter(bus__iexact=bus).exists(),
           'La placa ya figura en otra salida ese día. Revise el cruce.', 409)
    exigir(not ocupadas.filter(
        Q(conductor_uno_id__in=(c1, c2)) | Q(conductor_dos_id__in=(c1, c2))
    ).exists(), 'Un conductor ya tiene una salida ese día. Revise el cruce.', 409)
    # Una ficha sin cuenta puede programarse; su asignación seguirá pendiente.
    perfiles = Perfil.objects.filter(
        conductor_id__in=(c1, c2), activo=True,
        usuario__is_active=True, usuario__esta_activo=True,
    )
    cuentas_vinculadas = perfiles.values('conductor_id').distinct().count() == 2
    lote = Importacion.objects.create(
        nombre='Programación manual · sin Excel',
        huella=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
        inicio=fecha, fin=fecha, estado='VALIDADO', creado_por=usuario,
        validado_por=usuario, validado=timezone.now(),
    )
    salida = Salida.objects.create(
        importacion=lote, fila=1, fecha=fecha, hora=hora, bus=bus,
        origen=origen, destino=destino,
        conductor_uno=conductores[c1], conductor_dos=conductores[c2],
        nombre_uno=conductores[c1].nombre,
        nombre_dos=conductores[c2].nombre,
        estado_operativo='PROGRAMADO', clave=clave, clave_confirmada=clave,
        original={'origen_programacion': 'MANUAL', 'comercial': {}},
    )
    op = Operacion.objects.create(salida=salida, estado='PROGRAMADO')
    publicada, motivo = comprobar_descanso(op) if cuentas_vinculadas else (
        False, 'Uno o ambos conductores no tienen cuenta móvil activa vinculada a su ficha.')
    if publicada:
        salida.original['publicacion_descanso_autorizada'] = True
        salida.original['firma_asignacion_publicada'] = firma_asignacion(salida)
        salida.save(update_fields=['original'])
    Auditoria.objects.create(
        actor=usuario, accion='programar_viaje_manual',
        detalle={'viaje': op.pk, 'salida': salida.pk, 'placa': bus,
                 'conductores': [c1, c2], 'publicada': publicada,
                 'motivo_revision': motivo},
    )
    return op, publicada, motivo


@transaction.atomic
def editar(datos, salida_id, usuario):
    """Edita una programación manual conservando pasajeros y distribución."""
    salida = Salida.objects.select_for_update().select_related(
        'importacion').get(pk=salida_id)
    exigir(salida.original.get('origen_programacion') == 'MANUAL',
           'Solo se pueden editar programaciones manuales.', 403)
    exigir(not salida.anulado and salida.estado_operativo == 'PROGRAMADO',
           'Este viaje ya no se puede editar.', 409)
    try:
        fecha = date.fromisoformat(datos.get('fecha', ''))
        hora = time.fromisoformat(datos.get('hora', ''))
        c1 = int(datos.get('conductor_uno', ''))
        c2 = int(datos.get('conductor_dos', ''))
    except (TypeError, ValueError) as exc:
        raise Problema('Complete fecha, hora y ambos conductores registrados.') from exc
    exigir(fecha >= timezone.localdate(), 'La programación histórica es solo lectura.')
    exigir(c1 != c2, 'Seleccione dos conductores distintos.')
    conductores = {c.pk: c for c in Conductor.objects.filter(pk__in=(c1, c2))}
    exigir(len(conductores) == 2, 'Seleccione conductores de las fichas existentes.')
    bus = referencia_registrada(str(datos.get('bus', '')).strip(), placas_disponibles())
    exigir(bus, 'Seleccione una placa de itinerarios validados.')
    sedes = sedes_disponibles()
    valor_origen = str(datos.get('origen', '')).strip()
    valor_destino = str(datos.get('destino', '')).strip()
    origen = referencia_registrada(valor_origen, sedes) or valor_origen
    destino = referencia_registrada(valor_destino, sedes) or valor_destino
    exigir(origen and destino and normalizar(sede(origen)) != normalizar(sede(destino)),
           'Seleccione sedes registradas distintas para origen y destino.')
    clave = hashlib.sha256('|'.join((
        fecha.isoformat(), hora.isoformat(), normalizar(bus),
        normalizar(origen), normalizar(destino),
    )).encode()).hexdigest()
    exigir(not Salida.objects.filter(clave_confirmada=clave).exclude(
        pk=salida.pk).exists(), 'La salida ya está programada. Revise la ficha existente.', 409)
    ocupadas = Salida.objects.filter(fecha=fecha, anulado=False).exclude(
        estado_operativo='CANCELADO').exclude(pk=salida.pk)
    exigir(not ocupadas.filter(bus__iexact=bus).exists(),
           'La placa ya figura en otra salida ese día. Revise el cruce.', 409)
    exigir(not ocupadas.filter(
        Q(conductor_uno_id__in=(c1, c2)) | Q(conductor_dos_id__in=(c1, c2))
    ).exists(), 'Un conductor ya tiene una salida ese día. Revise el cruce.', 409)
    anterior = {
        'fecha': str(salida.fecha), 'hora': salida.hora.isoformat(),
        'bus': salida.bus, 'origen': salida.origen, 'destino': salida.destino,
        'conductores': [salida.conductor_uno_id, salida.conductor_dos_id],
    }
    salida.fecha = fecha
    salida.hora = hora
    salida.bus = bus
    salida.origen = origen
    salida.destino = destino
    salida.conductor_uno = conductores[c1]
    salida.conductor_dos = conductores[c2]
    salida.nombre_uno = conductores[c1].nombre
    salida.nombre_dos = conductores[c2].nombre
    salida.clave = clave
    salida.clave_confirmada = clave
    # La firma de publicación solo vale para la asignación anterior.
    salida.original.pop('publicacion_descanso_autorizada', None)
    salida.original.pop('firma_asignacion_publicada', None)
    salida.save()
    salida.importacion.inicio = fecha
    salida.importacion.fin = fecha
    salida.importacion.save(update_fields=['inicio', 'fin'])
    op, _ = Operacion.objects.get_or_create(
        salida=salida, defaults={'estado': 'PROGRAMADO'})
    perfiles = Perfil.objects.filter(
        conductor_id__in=(c1, c2), activo=True,
        usuario__is_active=True, usuario__esta_activo=True,
    )
    cuentas_vinculadas = perfiles.values('conductor_id').distinct().count() == 2
    publicada, motivo = comprobar_descanso(op) if cuentas_vinculadas else (
        False, 'Uno o ambos conductores no tienen cuenta móvil activa vinculada a su ficha.')
    if publicada:
        salida.original['publicacion_descanso_autorizada'] = True
        salida.original['firma_asignacion_publicada'] = firma_asignacion(salida)
        salida.save(update_fields=['original'])
    Auditoria.objects.create(
        actor=usuario, accion='editar_viaje_manual',
        detalle={'salida': salida.pk, 'viaje': op.pk, 'anterior': anterior,
                 'nuevo': {'fecha': str(fecha), 'hora': hora.isoformat(),
                           'placa': bus, 'conductores': [c1, c2]},
                 'publicada': publicada, 'motivo_revision': motivo},
    )
    return op, publicada, motivo


def comprobar_descanso(op):
    """Comprueba 8 h de ambos sin activar la regla global de publicación."""
    from .descanso_publicacion import EvaluadorPublicacionLote
    from .models import ReglaDescanso
    perfiles = {
        p.conductor_id: p for p in Perfil.objects.filter(
            conductor_id__in=(op.salida.conductor_uno_id, op.salida.conductor_dos_id),
            activo=True,
        ).select_related('usuario')
    }
    evaluador = EvaluadorPublicacionLote([op], ReglaDescanso(horas=8))
    razones = []
    for c in (op.salida.conductor_uno, op.salida.conductor_dos):
        ok, motivo = evaluador.evaluar(op, perfiles.get(c.pk))
        if not ok:
            razones.append(f'{c.nombre_apellidos}: {motivo}')
    return not razones, ' '.join(razones)


def _publicar_descanso(salida_id, usuario, accion):
    """Valida, firma, guarda y audita la publicación; la transacción la impone el llamador."""
    salida = Salida.objects.select_for_update().get(
        pk=salida_id, original__origen_programacion='MANUAL')
    op = Operacion.objects.select_for_update().get(salida=salida)
    exigir(op.estado == 'PROGRAMADO' and not salida.anulado
           and salida.estado_operativo != 'CANCELADO',
           'Este viaje ya no se puede publicar.', 409)
    exigir(salida.fecha >= timezone.localdate(),
           'Los viajes históricos son de solo lectura.', 409)
    publicada, motivo = comprobar_descanso(op)
    exigir(publicada, motivo or 'No se pudo comprobar el descanso.', 409)
    salida.original['publicacion_descanso_autorizada'] = True
    salida.original['firma_asignacion_publicada'] = firma_asignacion(salida)
    salida.save(update_fields=['original'])
    Auditoria.objects.create(
        actor=usuario, accion=accion,
        detalle={'salida': salida.pk, 'viaje': op.pk,
                 'conductores': [salida.conductor_uno_id, salida.conductor_dos_id]},
    )
    return op


@transaction.atomic
def publicar_pendiente(salida_id, usuario):
    """Solo Control confirma una programación manual pendiente, con auditoría."""
    from .views import GESTION
    exigir(usuario.rol in GESTION, 'Solo Control puede revisar el descanso.', 403)
    return _publicar_descanso(
        salida_id, usuario, 'publicar_programacion_manual')


@transaction.atomic
def publicar_automatico(salida_id, usuario):
    """Publica si ambos conductores ya tienen 8 h desde su llegada real."""
    return _publicar_descanso(
        salida_id, usuario, 'publicar_descanso_automatico')
