"""La API aplica la misma política de contraseñas que el resto del sistema."""
from types import SimpleNamespace

from django.test import TestCase
from ninja.errors import HttpError

from core.api import cambiar_password, crear_usuario
from core.models import Usuario
from core.schemas import CambiarPasswordSchema, UsuarioCreateSchema


class PoliticaContrasenasTests(TestCase):
    def test_cambiar_password_rechaza_clave_debil(self):
        usuario = Usuario.objects.create_user(
            'clave-actual', dni='25252525', rol='CONTADORA',
            password='ClaveActual2026!')
        peticion = SimpleNamespace(auth=usuario)
        with self.assertRaises(HttpError) as error:
            cambiar_password(peticion, CambiarPasswordSchema(
                old_password='ClaveActual2026!', new_password='abc123'))
        self.assertIn('contraseña', error.exception.message.lower())

    def test_crear_usuario_rechaza_clave_debil(self):
        datos = UsuarioCreateSchema(
            dni='26262626', username='nuevo-debil', password='abc123',
            first_name='Nuevo', last_name='Debil', rol='CONTADORA')
        with self.assertRaises(HttpError) as error:
            crear_usuario(None, datos)
        self.assertIn('contraseña', error.exception.message.lower())
