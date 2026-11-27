import os
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError


@override_settings(ROOT_URLCONF='deploy.test_urls')
class DeploymentTests(TestCase):
    def test_health_no_requiere_login(self):
        response=self.client.get('/health/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content,b'ok')

    def test_bootstrap_idempotente_no_reinicia_clave(self):
        env={'BOOTSTRAP_ADMIN_USERNAME':'admin_de_prueba','BOOTSTRAP_ADMIN_PASSWORD':'InicialPruebaSegura2026!','BOOTSTRAP_ADMIN_EMAIL':'prueba@example.invalid'}
        with patch.dict(os.environ,env):
            call_command('bootstrap_admin',stdout=StringIO())
            u=get_user_model().objects.get(username='admin_de_prueba')
            self.assertTrue(u.is_superuser)
            u.set_password('ClaveCambiada2026!');u.save(update_fields=['password'])
            call_command('bootstrap_admin',stdout=StringIO())
            u.refresh_from_db();self.assertTrue(u.check_password('ClaveCambiada2026!'))
            self.assertEqual(get_user_model().objects.filter(username=u.username).count(),1)

    def test_bootstrap_rechaza_clave_debil(self):
        with patch.dict(os.environ,{'BOOTSTRAP_ADMIN_USERNAME':'admin_invalido','BOOTSTRAP_ADMIN_PASSWORD':'1234'}):
            with self.assertRaises(CommandError):call_command('bootstrap_admin',stdout=StringIO())
        self.assertFalse(get_user_model().objects.filter(username='admin_invalido').exists())

    def test_media_exige_sesion_y_permisos_y_no_permite_recorrido(self):
        with tempfile.TemporaryDirectory() as d,override_settings(MEDIA_ROOT=d):
            Path(d,'privado.txt').write_text('archivo sintético',encoding='utf-8')
            self.assertEqual(self.client.get('/media/privado.txt').status_code,302)
            u=get_user_model().objects.create_user(username='persona_media',dni=None,email='persona@example.invalid')
            self.client.force_login(u)
            self.assertEqual(self.client.get('/media/privado.txt').status_code,404)
            u.rol='CONTADORA';u.save(update_fields=['rol'])
            response=self.client.get('/media/privado.txt')
            self.assertEqual(response.status_code,200)
            self.assertIn('attachment',response['Content-Disposition']);response.close()
            self.assertEqual(self.client.get('/media/../externo.txt').status_code,404)
