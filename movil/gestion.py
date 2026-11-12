"""Acciones de ventas y administración con controles compartidos por la app."""
import base64
import csv
import io
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.files.base import ContentFile
from django.db.models import Q
from django.utils import timezone
from .models import *
from .views import exigir, rol, GESTION, VENTAS, Problema, fecha, instante, hash_token, disponibilidad, aviso_operacion, publicar_marca

def gestionar(accion, p, d):
    if accion == 'asignar_embarque':
        rol(p,VENTAS)
        op=Operacion.objects.select_for_update().select_related('salida').get(pk=d['viaje'])
        exigir(op.estado in ['PROGRAMADO','EN_CURSO'],'El viaje ya está cerrado.',409)
        encargado=Perfil.objects.select_related('usuario').get(pk=d['perfil'],activo=True,usuario__is_active=True,usuario__esta_activo=True)
        from .views import asignado
        exigir(encargado.usuario.rol=='OPERADOR_EMBARQUE' or asignado(op,encargado),'Seleccione un embarcador o un conductor asignado al viaje.')
        op.embarcadores.set([encargado])
        op.permite_embarque_conductor=bool(d.get('conductores'))
        op.save(update_fields=['permite_embarque_conductor'])
        Aviso.objects.create(perfil=encargado,texto=f'Embarque asignado: {op.salida.fecha} {op.salida.origen} → {op.salida.destino}.')
        Auditoria.objects.create(actor=p.usuario,accion=accion,detalle={'viaje':op.pk,'perfil':encargado.pk})
        return {'mensaje':'Responsable de embarque asignado.'}
    if accion == 'importar_itinerario':
        rol(p, VENTAS)
        from conductores.parser import extraer
        from conductores.services import buscar_conductor
        from conductores.models import Importacion, Salida
        contenido = base64.b64decode(d['contenido'], validate=True)
        huella = hashlib.sha256(contenido).hexdigest()
        existente = Importacion.objects.filter(huella=huella).first()
        if existente: return {'mensaje': 'El archivo ya se había importado.', 'repetido': True}
        archivo = ContentFile(contenido, name=str(d['nombre'])[:200])
        exigir(archivo.name.lower().endswith(('.xls', '.xlsx')), 'Seleccione un archivo Excel.')
        filas, errores = extraer(archivo)
        exigir(filas and not errores, 'Reporte inválido: ' + '; '.join(map(str, errores[:5])))
        exigir(len(filas) <= 10000, 'Máximo 10000 filas por archivo.')
        reconocidos = {}
        for f in filas:
            if not f['anulado']:
                for campo in ('nombre_uno', 'nombre_dos'):
                    reconocidos[f[campo]] = buscar_conductor(f[campo])
                    exigir(reconocidos[f[campo]], f'Conductor no identificado: {f[campo]}. Vincule su ficha en SISMOC.')
                exigir(reconocidos[f['nombre_uno']] != reconocidos[f['nombre_dos']], 'El mismo conductor figura en ambos puestos.')
        lote = Importacion.objects.create(nombre=archivo.name, huella=huella, inicio=min(f['fecha'] for f in filas), fin=max(f['fecha'] for f in filas), creado_por=p.usuario, estado='VALIDADO', validado_por=p.usuario, validado=timezone.now())
        nuevas = repetidas = 0
        claves = set()
        for f in filas:
            exigir(f['clave'] not in claves, f"Fila {f['fila']}: salida repetida dentro del archivo.")
            claves.add(f['clave'])
            # Un cambio de hora o bus no se presume un viaje nuevo: se devuelve conflicto
            # si coincide la fecha, ruta y pareja pero no existe ID externo estable.
            previa = Salida.objects.filter(clave_confirmada=f['clave']).first()
            if previa:
                repetidas += 1
                continue
            c1, c2 = reconocidos.get(f['nombre_uno']), reconocidos.get(f['nombre_dos'])
            ambiguas = Salida.objects.filter(fecha=f['fecha'], origen=f['origen'], destino=f['destino'], conductor_uno=c1, conductor_dos=c2, clave_confirmada__isnull=False)
            exigir(not ambiguas.exists(), f"Fila {f['fila']}: posible modificación de viaje existente. Revise en el sistema para evitar duplicados.", 409)
            s = Salida.objects.create(importacion=lote, conductor_uno=c1, conductor_dos=c2, clave_confirmada=f['clave'], estado_operativo='CANCELADO' if f['anulado'] else 'PROGRAMADO', **f)
            Operacion.objects.create(salida=s, estado='CANCELADO' if s.anulado else 'PROGRAMADO')
            nuevas += 1
            if not s.anulado:
                aviso_operacion(Operacion.objects.get(salida=s), f'Viaje asignado: {s.fecha} {s.hora:%H:%M}, {s.origen} → {s.destino}.')
        archivo.seek(0); lote.archivo.save(huella+'.'+archivo.name.rsplit('.',1)[-1], archivo)
        Auditoria.objects.create(actor=p.usuario, accion=accion, detalle={'lote': lote.pk, 'nuevas': nuevas, 'repetidas': repetidas})
        return {'mensaje': f'{nuevas} salidas incorporadas; {repetidas} ya existentes conservadas.'}
    if accion == 'asignar':
        rol(p, VENTAS)
        op = Operacion.objects.select_for_update().select_related('salida').get(pk=d['viaje'])
        exigir(op.estado == 'PROGRAMADO', 'Solo puede cambiar una salida programada.', 409)
        a, b = Perfil.objects.get(pk=d['uno']), Perfil.objects.get(pk=d['dos'])
        exigir(a.pk != b.pk and a.conductor_id and b.conductor_id and a.activo and b.activo, 'Seleccione dos conductores distintos y activos.')
        s = op.salida
        inicio = timezone.make_aware(datetime.combine(s.fecha,s.hora), timezone.get_default_timezone())
        fin = instante(d['fin_previsto'])
        exigir(inicio < fin <= inicio+timedelta(days=2), 'Indique una llegada prevista válida para comprobar cruces.')
        for candidato in (a,b):
            disponible = disponibilidad(candidato, inicio)
            exigir(disponible['permitido'], disponible['mensaje'], 409)
            for otra in Operacion.objects.exclude(pk=op.pk).exclude(estado='CANCELADO').filter(Q(salida__conductor_uno_id=candidato.conductor_id) | Q(salida__conductor_dos_id=candidato.conductor_id)).select_related('salida'):
                otro_inicio = timezone.make_aware(datetime.combine(otra.salida.fecha, otra.salida.hora), timezone.get_default_timezone())
                if otra.estado == 'EN_CURSO' or (otro_inicio < fin and (otra.fin_previsto or otro_inicio+timedelta(hours=12)) > inicio):
                    raise Problema('Hay un viaje que cruza con la asignación. Revise sus horas.',409)
        s.conductor_uno, s.conductor_dos = a.conductor,b.conductor
        s.save(update_fields=['conductor_uno','conductor_dos'])
        op.fin_previsto, op.cambio_manual = fin, True
        op.permite_embarque_conductor = bool(d.get('embarque_conductor'))
        op.save()
        aviso_operacion(op, f'Asignación actualizada: {s.fecha} {s.origen} → {s.destino}.')
        Auditoria.objects.create(actor=p.usuario, accion=accion, detalle={'viaje':op.pk,'uno':a.pk,'dos':b.pk})
        return {'mensaje':'Conductores asignados.'}
    if accion == 'importar_pasajeros':
        rol(p, VENTAS)
        op = Operacion.objects.select_for_update().select_related('salida').get(pk=d['viaje'])
        filas = list(csv.DictReader(io.StringIO(d['csv'].lstrip('\ufeff'))))
        campos = {'referencia','nombre','documento','piso','asiento','origen','destino','punto'}
        exigir(filas and len(filas)<=300 and campos <= set(filas[0]), 'CSV requerido: referencia,nombre,documento,piso,asiento,origen,destino,punto.')
        vistos = set(); nuevos = 0
        for f in filas:
            ref = f['referencia'].strip()
            exigir(ref and ref not in vistos, 'Referencia vacía o repetida.')
            vistos.add(ref)
            piso, asiento = int(f['piso']), int(f['asiento'])
            exigir(piso in (1,2) and 1<=asiento<=100, 'Piso o asiento inválido.')
            actual = Pasajero.objects.filter(operacion=op, referencia=ref).first()
            datos = {k: str(f[k]).strip() for k in campos-{'referencia','piso','asiento'}}
            exigir(datos['nombre'] and datos['documento'], 'Falta nombre o documento.')
            datos.update(piso=piso,asiento=asiento)
            if actual:
                exigir(all(getattr(actual,k)==v for k,v in datos.items()), f'Reserva {ref} modificada: revisión manual requerida. Se conserva el embarque.',409)
            else:
                exigir(op.estado == 'PROGRAMADO', 'Nuevas reservas en viajes iniciados requieren revisión manual.',409)
                # Hasta disponer de los tramos de la empresa, no se asume reutilización segura.
                exigir(not op.pasajeros.filter(piso=piso,asiento=asiento).exists(), 'Asiento repetido: falta información de tramos para permitir reutilización.',409)
                Pasajero.objects.create(operacion=op, referencia=ref, **datos); nuevos += 1
        aviso_operacion(op, f'Lista de pasajeros actualizada: {op.salida.origen} → {op.salida.destino}. Revise los puntos de embarque.')
        return {'mensaje': f'{nuevos} pasajeros añadidos. Los registros anteriores se conservaron.'}
    if accion == 'resolver_incidencia':
        rol(p, VENTAS)
        i = Incidencia.objects.get(pk=d['id'])
        exigir(d['estado'] in ['RECIBIDO','EN_ATENCION','RESUELTO'], 'Estado inválido.')
        i.estado=d['estado']; i.save()
        Aviso.objects.create(perfil=i.perfil, texto=f'Incidencia {i.pk}: {i.estado}.')
        return {'mensaje':'Reporte actualizado.'}
    if accion == 'revisar_solicitud':
        rol(p,GESTION)
        s=Solicitud.objects.select_for_update().select_related('perfil').get(pk=d['id'])
        exigir(s.perfil_id != p.pk,'No puede aprobar su propia solicitud.',403)
        exigir(s.estado=='PENDIENTE','La solicitud ya fue revisada.',409)
        aprobar=d.get('aprobar') is True
        if aprobar:
            # Serialize approvals with attendance marking for this account.
            Perfil.objects.select_for_update(of=('self',)).get(pk=s.perfil_id)
            exigir(s.perfil.trabajador_id or (s.perfil.conductor_id and s.tipo in ['VACACIONES','PERMISO']),'Vincule primero al trabajador.')
            if s.tipo=='CAMBIO_HORARIO':
                from asistencia.models import ProgramacionHorario, TurnoHorario
                turno_id=s.datos.get('turno') or d.get('turno')
                exigir(turno_id,'La solicitud no indica un turno. Configure el cambio en Asistencia antes de aprobarlo.')
                turno=TurnoHorario.objects.get(pk=turno_id,activo=True)
                dia=s.desde
                while dia<=s.hasta:
                    ProgramacionHorario.objects.update_or_create(trabajador=s.perfil.trabajador,fecha=dia,defaults={'turno':turno,'motivo':s.detalle,'responsable':p.usuario})
                    dia+=timedelta(days=1)
            elif s.tipo in ['VACACIONES','PERMISO'] and s.perfil.conductor_id:
                from conductores.services import registrar_situacion
                registrar_situacion(s.perfil.conductor,s.desde,s.hasta,s.tipo,s.detalle,p.usuario)
                if s.tipo=='VACACIONES' and s.perfil.trabajador_id:
                    from asistencia.models import PeriodoVacaciones
                    exigir(not PeriodoVacaciones.objects.filter(trabajador=s.perfil.trabajador,desde__lte=s.hasta,hasta__gte=s.desde).exists(),'Ya existe un período de vacaciones que cruza estas fechas.',409)
                    PeriodoVacaciones.objects.create(trabajador=s.perfil.trabajador,desde=s.desde,hasta=s.hasta,creado_por=p.usuario,aprobado_por=p.usuario,aprobado_el=timezone.now())
            elif s.tipo=='VACACIONES':
                from asistencia.models import PeriodoVacaciones
                exigir(not PeriodoVacaciones.objects.filter(trabajador=s.perfil.trabajador,desde__lte=s.hasta,hasta__gte=s.desde).exists(),'Ya existe un período de vacaciones que cruza estas fechas.',409)
                PeriodoVacaciones.objects.create(trabajador=s.perfil.trabajador,desde=s.desde,hasta=s.hasta,creado_por=p.usuario,aprobado_por=p.usuario,aprobado_el=timezone.now())
            elif s.tipo=='PERMISO':
                from asistencia.models import ResumenAsistenciaDiaria
                from asistencia.services.aprobacion_situacion import aprobar_situacion_del_dia
                dia=s.desde
                while dia<=s.hasta:
                    resumen,_=ResumenAsistenciaDiaria.objects.get_or_create(trabajador=s.perfil.trabajador,fecha=dia)
                    aprobar_situacion_del_dia(resumen,p.usuario,'PERMISO',s.detalle)
                    dia+=timedelta(days=1)
            else:
                # Aprobación económica requiere el flujo existente de revisión de jornadas.
                raise Problema('Aplique primero la corrección o permiso en la revisión de Asistencia. Esta solicitud se conserva pendiente para no simular una aprobación.')
        s.estado='APROBADO' if aprobar else 'RECHAZADO'
        s.respuesta=str(d.get('respuesta',''))[:2000]; s.revisado_por=p.usuario; s.save()
        Aviso.objects.create(perfil=s.perfil,texto=f'Solicitud {s.pk}: {s.estado}. {s.respuesta[:300]}')
        Auditoria.objects.create(actor=p.usuario,accion=accion,detalle={'solicitud':s.pk,'estado':s.estado})
        return {'mensaje':'Solicitud revisada.'}
    if accion == 'revisar_marca':
        raise Problema('Revise las marcaciones en el detalle diario de Asistencia.',403)
    raise Problema('Acción no encontrada.',404)

