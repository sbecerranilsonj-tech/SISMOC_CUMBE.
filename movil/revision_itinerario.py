"""Revisión explícita de diferencias, vinculada a la sesión y al estado original."""
import hashlib
import json
import secrets
import time
from datetime import date, time as hora
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from conductores.models import Salida, Importacion, almacen_itinerarios
from conductores.parser import normalizar
from conductores.services import buscar_conductor
from .models import Operacion, Auditoria, Pasajero
from .views import exigir

CAMPOS={'Fecha':('fecha','date'),'Hora':('hora','time'),'Bus':('bus','text'),'Origen':('origen','text'),'Destino':('destino','text'),'Conductor 1':('nombre_uno','text'),'Conductor 2':('nombre_dos','text'),'Anulación':('anulado','boolean'),'Capacidad':('capacidad','number'),'Ventas piso 1':('vendidos_primer_piso','number'),'Ventas piso 2':('vendidos_segundo_piso','number')}
COMERCIALES={'capacidad','vendidos_primer_piso','vendidos_segundo_piso'}


def huella_salida(s):
    datos={k:getattr(s,k) for k in ('fecha','hora','bus','origen','destino','nombre_uno','nombre_dos','anulado','original','conductor_uno_id','conductor_dos_id','clave_confirmada')}
    return hashlib.sha256(json.dumps(datos,sort_keys=True,cls=DjangoJSONEncoder).encode()).hexdigest()


def descartar(session):
    revision=session.pop('revision_itinerario',None)
    if revision and revision.get('documento'):almacen_itinerarios().delete(revision['documento'])


def preparar(session,nombre,filas,comparacion,contenido):
    from django.core.files.base import ContentFile
    descartar(session)
    cambios=[c for c in comparacion if c['estado'] in ('CAMBIO','CONFLICTO','PENDIENTE')]
    for c in cambios:
        if c['salida_id']:
            anterior=Salida.objects.get(pk=c['salida_id'])
            c['huella']=huella_salida(anterior)
            c['registrada']={
                'fecha':str(anterior.fecha),'hora':str(anterior.hora),
                'bus':anterior.bus,'origen':anterior.origen,'destino':anterior.destino,
                'conductor_uno':anterior.nombre_uno,'conductor_dos':anterior.nombre_dos,
            }
            propuesta=next(f for f in filas if f['fila']==c['fila'])
            c['excel']={
                'fecha':str(propuesta['fecha']),'hora':str(propuesta['hora']),
                'bus':propuesta['bus'],'origen':propuesta['origen'],'destino':propuesta['destino'],
                'conductor_uno':propuesta['nombre_uno'],'conductor_dos':propuesta['nombre_dos'],
            }
        for d in c['diferencias']:
            if d['campo'] in CAMPOS:
                campo,tipo=CAMPOS[d['campo']];d.update(codigo=campo,tipo=tipo,valor='' if d['despues']=='None' else d['despues'])
    revision={'archivo':nombre,'token':secrets.token_urlsafe(24),'vence':time.time()+3600,'filas':json.loads(json.dumps(filas,cls=DjangoJSONEncoder)),'cambios':cambios,'bloqueada':any(c['estado']!='CAMBIO' for c in cambios),'sha256':hashlib.sha256(contenido).hexdigest()}
    revision['documento']=almacen_itinerarios().save('revisiones/'+secrets.token_hex(24)+'.'+nombre.rsplit('.',1)[-1],ContentFile(contenido))
    session['revision_itinerario']=revision


@transaction.atomic
def validar(session,post,usuario):
    revision=session.get('revision_itinerario')
    exigir(revision and secrets.compare_digest(str(post.get('revision','')),revision['token']),'La revisión ya no está disponible. Suba el archivo nuevamente.')
    exigir(revision['vence']>time.time(),'La revisión venció. Suba el archivo nuevamente.')
    exigir(not revision['bloqueada'],'Hay coincidencias ambiguas o reportes pendientes. Corrija o valide el reporte original.')
    filas={f['fila']:dict(f) for f in revision['filas']}
    salidas={}
    conservadas=0
    for c in revision['cambios']:
        s=Salida.objects.select_for_update().get(pk=c['salida_id'])
        exigir(huella_salida(s)==c['huella'],'El itinerario cambió desde la comparación. Suba el archivo otra vez para revisar la versión actual.',409)
        eleccion=post.get(f"eleccion_{c['fila']}",'corregir')
        exigir(eleccion in ('conservar','excel','corregir'),'Seleccione qué ficha conservar.')
        if eleccion=='conservar':
            conservadas+=1
            continue
        op=Operacion.objects.select_for_update().filter(salida=s).first()
        exigir(not op or op.estado=='PROGRAMADO','Solo se pueden actualizar viajes que aún no han iniciado.',409)
        f=filas[c['fila']]
        for d in c['diferencias']:
            campo,tipo=CAMPOS[d['campo']]
            valor=(('' if d['despues']=='None' else str(d['despues']))
                   if eleccion=='excel'
                   else post.get(f"c_{c['fila']}_{campo}",'').strip())
            if tipo=='date':valor=date.fromisoformat(valor).isoformat()
            elif tipo=='time':valor=hora.fromisoformat(valor).isoformat()
            elif tipo=='boolean':
                exigir(valor in ('True','False'),'Seleccione un estado de anulación válido.');valor=valor=='True'
            elif tipo=='number':
                valor=int(valor) if valor else None
                exigir(valor is None or 0<=valor<=1000,'Las ventas y la capacidad deben estar entre 0 y 1000.')
            else:exigir(bool(valor) and len(valor)<=180,'Complete los datos del viaje, con un máximo de 180 caracteres.')
            if campo in COMERCIALES:f['original'].setdefault('comercial',{})[campo]=valor
            else:f[campo]=valor
        estructural=any(d['codigo'] not in COMERCIALES for d in c['diferencias'])
        exigir(not (op and estructural and (op.cambio_manual or Pasajero.objects.filter(operacion=op).exists())),'El viaje tiene asignaciones manuales o pasajeros. Revíselo antes de modificar sus datos operativos.',409)
        salidas[c['fila']]=s
    claves=set()
    for numero in list(filas):
        if any(c['fila']==numero and post.get(f"eleccion_{numero}")=='conservar'
               for c in revision['cambios']):
            filas.pop(numero)
    for f in filas.values():
        f['fecha']=date.fromisoformat(f['fecha']);f['hora']=hora.fromisoformat(f['hora'])
        f['clave']=hashlib.sha256('|'.join((f['fecha'].isoformat(),f['hora'].isoformat(),normalizar(f['bus']),normalizar(f['origen']),normalizar(f['destino']))).encode()).hexdigest()
        exigir(f['clave'] not in claves,'Las correcciones generan viajes duplicados. Revise fecha, hora, bus y recorrido.');claves.add(f['clave'])
        datos=f['original'].get('comercial',{})
        capacidad=datos.get('capacidad');v1=datos.get('vendidos_primer_piso');v2=datos.get('vendidos_segundo_piso')
        exigir(capacidad is None or v1 is None or v2 is None or v1+v2<=capacidad,'El total vendido supera la capacidad del bus.')
    for numero,s in salidas.items():
        f=filas[numero]
        exigir(not Salida.objects.exclude(pk=s.pk).filter(clave_confirmada=f['clave']).exists(),'Ya existe otra salida con esos datos.',409)
        if not f['anulado']:
            a,b=buscar_conductor(f['nombre_uno']),buscar_conductor(f['nombre_dos'])
            exigir(a and b and a.pk!=b.pk,'Seleccione dos conductores registrados y distintos.')
            # Cambios de hora, fecha o conductores requieren revisar cruces antes de actualizar.
            if (s.fecha,s.hora,s.conductor_uno_id,s.conductor_dos_id)!=(f['fecha'],f['hora'],a.pk,b.pk):
                from django.db.models import Q
                exigir(not Salida.objects.exclude(pk=s.pk).filter(fecha=f['fecha'],anulado=False).exclude(estado_operativo='CANCELADO').filter(Q(conductor_uno__in=[a,b])|Q(conductor_dos__in=[a,b])).exists(),'Un conductor tiene otros viajes ese día. Revise la asignación antes de cambiar fecha, hora o conductores.',409)
            s.conductor_uno,s.conductor_dos=a,b
        antes=huella_salida(s)
        for campo in ('fecha','hora','bus','origen','destino','nombre_uno','nombre_dos','anulado','original','clave'):setattr(s,campo,f[campo])
        if s.importacion.estado=='VALIDADO':s.clave_confirmada=s.clave
        if s.anulado:s.estado_operativo='CANCELADO'
        s.full_clean();s.save()
        if s.anulado:Operacion.objects.filter(salida=s).update(estado='CANCELADO')
        Auditoria.objects.create(actor=usuario,accion='validar_cambio_itinerario',detalle={'salida':s.pk,'archivo':revision['archivo'],'documento':revision['documento'],'sha256':revision['sha256'],'antes':antes,'despues':huella_salida(s)})
    # Las filas nuevas se incorporan al mismo flujo; las coincidencias conservan su registro.
    from .comparacion_itinerarios import comparar_filas
    nuevas=[f for f,c in zip(filas.values(),comparar_filas(list(filas.values()))) if c['estado']=='NUEVO']
    if nuevas:
        lote=Importacion.objects.filter(huella=revision['sha256']).first()
        if not lote:lote=Importacion.objects.create(nombre=revision['archivo'],huella=revision['sha256'],archivo=revision['documento'],inicio=min(f['fecha'] for f in nuevas),fin=max(f['fecha'] for f in nuevas),estado='VALIDADO',creado_por=usuario,validado_por=usuario,validado=timezone.now())
        for f in nuevas:
            a,b=buscar_conductor(f['nombre_uno']),buscar_conductor(f['nombre_dos'])
            exigir(f['anulado'] or (a and b and a.pk!=b.pk),'Hay conductores nuevos sin identificar.')
            s=Salida.objects.create(importacion=lote,conductor_uno=a,conductor_dos=b,clave_confirmada=f['clave'],estado_operativo='CANCELADO' if f['anulado'] else 'PROGRAMADO',**f)
            Operacion.objects.create(salida=s,estado='CANCELADO' if s.anulado else 'PROGRAMADO')
    session.pop('revision_itinerario',None)
    return len(salidas),len(nuevas)
