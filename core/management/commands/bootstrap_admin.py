"""Crear una sola cuenta administrativa desde secretos del alojamiento."""
import os
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Crea el administrador inicial si se proporcionan BOOTSTRAP_ADMIN_*; no modifica cuentas existentes.'

    @transaction.atomic
    def handle(self,*args,**options):
        username=os.getenv('BOOTSTRAP_ADMIN_USERNAME','').strip()
        password=os.getenv('BOOTSTRAP_ADMIN_PASSWORD','')
        if not username and not password:
            self.stdout.write('Sin bootstrap: puede crear el administrador con createsuperuser.')
            return
        if not username or not password:
            raise CommandError('Configure BOOTSTRAP_ADMIN_USERNAME y BOOTSTRAP_ADMIN_PASSWORD juntos.')
        User=get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write('La cuenta inicial ya existe; se conserva su contraseña y configuración.')
            return
        if len(password)<12:
            raise CommandError('La contraseña inicial debe tener al menos 12 caracteres.')
        user=User(username=username,email=os.getenv('BOOTSTRAP_ADMIN_EMAIL','').strip())
        validate_password(password,user)
        User.objects.create_superuser(username=username,email=user.email,password=password,dni=None)
        self.stdout.write(self.style.SUCCESS('Administrador inicial creado. Retire BOOTSTRAP_ADMIN_PASSWORD de Railway.'))
