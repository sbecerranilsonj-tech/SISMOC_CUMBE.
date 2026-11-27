import secrets
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from movil.models import Perfil, Sesion, Auditoria

class Command(BaseCommand):
    help='Habilita una cuenta existente y emite un código de activación válido por 24 horas.'
    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--trabajador',type=int)
        parser.add_argument('--conductor',type=int)
        parser.add_argument('--restablecer',action='store_true')
    def handle(self,*args,**o):
        try: u=get_user_model().objects.get(username=o['username'])
        except get_user_model().DoesNotExist: raise CommandError('El usuario debe existir en SISMOC.')
        p,nuevo=Perfil.objects.get_or_create(usuario=u)
        if p.activado and not o['restablecer']: raise CommandError('Ya activado. Use --restablecer si se perdió el teléfono.')
        if o['trabajador']: p.trabajador_id=o['trabajador']
        if o['conductor']: p.conductor_id=o['conductor']
        from movil.activacion import nuevo_codigo
        codigo=nuevo_codigo(p)
        p.activado=False; p.dispositivo=''; p.activo=True
        p.activacion_hash=make_password(codigo); p.activacion_hasta=timezone.now()+timedelta(hours=24)
        p.full_clean(exclude=['codigo']); p.save()
        Sesion.objects.filter(perfil=p).update(activa=False)
        Auditoria.objects.create(actor=u,accion='habilitar_app',detalle={'perfil':p.pk,'restablecido':o['restablecer']})
        self.stdout.write(f'Código del trabajador: {p.codigo}\nActivación (24 horas, un uso): {codigo}')
