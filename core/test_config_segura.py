"""Los ajustes de despliegue exigen claves reales y sin comodín."""
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class ConfigSeguraTests(SimpleTestCase):
    def test_sin_claves_el_arranque_falla(self):
        entorno = {**os.environ,
                   'SISMOC_LOAD_DOTENV': 'False',
                   'DEBUG': 'False',
                   'DJANGO_SETTINGS_MODULE': 'config.settings'}
        entorno.pop('SECRET_KEY', None)
        entorno.pop('JWT_SIGNING_KEY', None)
        resultado = subprocess.run(
            [sys.executable, '-c', 'import config.settings'],
            cwd=settings.BASE_DIR, env=entorno, capture_output=True, text=True)
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('SECRET_KEY', resultado.stderr)

    def test_clave_jwt_independiente_y_cors_cerrado(self):
        self.assertTrue(hasattr(settings, 'JWT_SIGNING_KEY'))
        self.assertGreaterEqual(len(settings.JWT_SIGNING_KEY), 32)
        self.assertNotEqual(settings.JWT_SIGNING_KEY, settings.SECRET_KEY)
        self.assertFalse(settings.CORS_ALLOW_ALL_ORIGINS)
