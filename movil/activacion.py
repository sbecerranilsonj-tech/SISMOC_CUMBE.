"""Activación por código temporal, separada del ingreso con contraseña."""
import secrets
from datetime import timedelta
from django.core import signing
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.http import JsonResponse
from django.utils import timezone
from .models import Perfil, IntentoAcceso, Sesion, Auditoria
from .views import exigir, hash_token, nombre

SALT = 'sismoc.activacion.v1'

def nuevo_codigo(perfil):
    return f'{perfil.pk}.{secrets.token_urlsafe(12)}'

def perfil_vigente(pk):
    return Perfil.objects.select_for_update(of=('self',)).select_related('usuario','trabajador').filter(
        pk=pk, activo=True, activado=False, usuario__is_active=True, usuario__esta_activo=True,
        activacion_hasta__gt=timezone.now()).first()

def ejecutar_activacion(accion, datos, direccion):
    dispositivo=str(datos.get('dispositivo',''))
    exigir(10<=len(dispositivo)<=100,'Dispositivo inválido.')
    if accion=='verificar_activacion':
        clave=hash_token('activar:'+str(direccion))
        intento,_=IntentoAcceso.objects.select_for_update().get_or_create(clave=clave,defaults={'desde':timezone.now()})
        if timezone.now()-intento.desde>timedelta(minutes=15):
            intento.intentos=0;intento.desde=timezone.now()
        exigir(intento.intentos<8,'Demasiados intentos de activación. Espere 15 minutos.',429)
        codigo=str(datos.get('activacion','')).strip()
        prefijo=codigo.partition('.')[0]
        p=perfil_vigente(int(prefijo)) if prefijo.isascii() and prefijo.isdigit() and len(prefijo)<=12 else None
        if not p or not check_password(codigo,p.activacion_hash):
            intento.intentos+=1;intento.save()
            return JsonResponse({'ok':False,'error':'Código de activación incorrecto o vencido. Use el último generado en la web.'},status=401)
        exigir(not p.dispositivo or p.dispositivo==dispositivo,'Cuenta vinculada a otro celular. Solicite restablecer el acceso.',403)
        intento.intentos=0;intento.save()
        ticket=signing.dumps({'perfil':p.pk,'dispositivo':dispositivo,'version':hash_token(p.activacion_hash)},salt=SALT)
        return {'codigo':p.codigo,'nombre':nombre(p),'ticket':ticket}
    try:
        prueba=signing.loads(str(datos.get('ticket','')),salt=SALT,max_age=600)
    except signing.BadSignature:
        exigir(False,'La validación venció. Ingrese nuevamente el código de activación.',401)
    exigir(prueba.get('dispositivo')==dispositivo,'La validación pertenece a otro teléfono.',403)
    p=perfil_vigente(prueba['perfil'])
    exigir(p and prueba.get('version')==hash_token(p.activacion_hash),'Código consumido, vencido o reemplazado. Genere una nueva activación.',401)
    exigir(not p.dispositivo or p.dispositivo==dispositivo,'Cuenta vinculada a otro teléfono.',403)
    password=str(datos.get('password',''))
    exigir(password==datos.get('confirmacion'),'Las contraseñas no coinciden.')
    exigir(8<=len(password)<=128,'La contraseña debe tener entre 8 y 128 caracteres.')
    validate_password(password,p.usuario)
    p.usuario.set_password(password);p.usuario.save(update_fields=['password'])
    p.activado=True;p.dispositivo=dispositivo;p.activacion_hash='';p.activacion_hasta=None;p.save()
    Sesion.objects.filter(perfil=p).update(activa=False)
    Auditoria.objects.create(actor=p.usuario,accion='activacion_completada',detalle={'perfil':p.pk})
    return {'codigo':p.codigo,'mensaje':'Contraseña creada. Inicie sesión para ingresar.'}
