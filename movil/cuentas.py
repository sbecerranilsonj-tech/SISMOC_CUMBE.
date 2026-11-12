"""Habilitar acceso desde una ficha existente, sin duplicar personas."""
import secrets
import re
from django.contrib.auth import get_user_model
from django.db import transaction
from asistencia.models import Trabajador
from conductores.models import Conductor
from .views import exigir, GESTION
from .models import Auditoria
from .models import Perfil


@transaction.atomic
def cuenta_para_ficha(trabajador_id, actor):
    ficha = Trabajador.objects.select_for_update(of=('self',)).select_related('usuario').get(pk=trabajador_id)
    exigir(re.fullmatch(r'[0-9]{8}', ficha.dni or ''), 'Complete el DNI de 8 dígitos en la ficha antes de habilitar el acceso.')
    if ficha.usuario_id:
        exigir(ficha.usuario.dni == ficha.dni, 'El DNI de la cuenta no coincide con la ficha. Revise la vinculación antes de continuar.')
        exigir(ficha.usuario.is_active and ficha.usuario.esta_activo, 'La cuenta está desactivada. Revise su estado antes de habilitar la app.')
        return ficha
    Usuario = get_user_model()
    usuario = Usuario.objects.select_for_update().filter(dni=ficha.dni).first()
    creado = False
    if usuario:
        exigir(not Trabajador.objects.exclude(pk=ficha.pk).filter(usuario=usuario).exists(), 'La cuenta ya está vinculada a otra ficha.')
        exigir(not usuario.is_staff and not usuario.is_superuser and usuario.rol not in GESTION,
               'Esta cuenta tiene permisos administrativos. Revise su vinculación desde administración.')
        exigir(usuario.is_active and usuario.esta_activo, 'La cuenta está desactivada; no se reactivará automáticamente.')
    else:
        conductor = Conductor.objects.filter(trabajador=ficha).exists()
        usuario = Usuario(username=f'app_{ficha.pk}_{secrets.token_hex(6)}', dni=ficha.dni,
            first_name=(ficha.nombres or ficha.nombre_completo)[:150],
            last_name=' '.join(filter(None, [ficha.apellido_paterno, ficha.apellido_materno]))[:150],
            email='', agencia_sede=ficha.sede, rol='CONDUCTOR' if conductor else 'ADMINISTRATIVO',
            is_staff=False, is_superuser=False)
        usuario.set_unusable_password()
        usuario.full_clean()
        usuario.save()
        creado = True
    ficha.usuario = usuario
    ficha.save(update_fields=['usuario'])
    Auditoria.objects.create(actor=actor, accion='cuenta_desde_ficha',
        detalle={'trabajador': ficha.pk, 'usuario': usuario.pk, 'cuenta_nueva': creado})
    return ficha

@transaction.atomic
def cuenta_para_conductor(conductor_id, dni, sede, actor):
    conductor=Conductor.objects.select_for_update(of=('self',)).get(pk=conductor_id)
    if conductor.trabajador_id:
        ficha=cuenta_para_ficha(conductor.trabajador_id,actor)
        return ficha.usuario,conductor,ficha
    existente=Perfil.objects.select_related('usuario','trabajador').filter(conductor=conductor).first()
    if existente:
        exigir(existente.usuario.is_active and existente.usuario.esta_activo,'La cuenta está desactivada.')
        return existente.usuario,conductor,existente.trabajador
    exigir(not dni or re.fullmatch(r'[0-9]{8}',dni),'Si ingresa DNI, debe tener 8 dígitos.')
    Usuario=get_user_model()
    usuario=Usuario.objects.select_for_update().filter(dni=dni).first() if dni else None
    if usuario:
        exigir(not Perfil.objects.filter(usuario=usuario).exists() and not Trabajador.objects.filter(usuario=usuario).exists(),
            'Ese DNI ya tiene una cuenta o ficha. Revise su vinculación antes de asignarlo al conductor.')
        exigir(usuario.rol=='CONDUCTOR' and not usuario.is_staff and not usuario.is_superuser and usuario.is_active and usuario.esta_activo,
            'La cuenta existente no es un acceso activo de conductor.')
    else:
        exigir(not dni or not Trabajador.objects.filter(dni=dni).exists(),'El DNI pertenece a una ficha de personal. Revise la identidad del conductor antes de vincularlo.')
        usuario=Usuario(username=f'conductor_{conductor.pk}_{secrets.token_hex(6)}',dni=dni or None,email='',
            first_name=(conductor.nombres or conductor.nombre)[:150],last_name=' '.join(filter(None,[conductor.apellido_paterno,conductor.apellido_materno]))[:150],
            agencia_sede='',rol='CONDUCTOR',is_staff=False,is_superuser=False)
        usuario.set_unusable_password();usuario.full_clean()
        usuario._solo_conductor=True
        usuario.save()
    Auditoria.objects.create(actor=actor,accion='cuenta_desde_conductor',detalle={'conductor':conductor.pk,'usuario':usuario.pk})
    return usuario,conductor,None

