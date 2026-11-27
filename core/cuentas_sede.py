"""Accesos compartidos para el panel, independientes de las fichas personales."""
import unicodedata
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction


def normalizar_sede(valor):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',valor) if not unicodedata.combining(c)).casefold().split())


@transaction.atomic
def crear_cuenta_sede(sede, username, password):
    sede=' '.join(sede.split());username=username.strip()
    if not sede or len(sede)>100 or not username:raise ValidationError('Indique sede y usuario válidos.')
    Usuario=get_user_model()
    grupo,_=Group.objects.get_or_create(name='Boletería por sede')
    Group.objects.select_for_update().get(pk=grupo.pk)
    if any(normalizar_sede(u.agencia_sede)==normalizar_sede(sede) for u in grupo.user_set.all()):
        raise ValidationError('Esta sede ya tiene una cuenta de Boletería. Use el acceso existente.')
    usuario=Usuario(username=username,rol='BOLETERIA',dni=None,email='',agencia_sede=sede,first_name='Boletería',last_name=sede)
    validate_password(password,usuario)
    usuario.set_password(password);usuario.full_clean();usuario.save();usuario.groups.add(grupo)
    return usuario
