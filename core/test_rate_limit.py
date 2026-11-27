"""Los intentos fallidos de login se limitan por IP e identificador."""
from django.core.cache import cache
from django.test import TestCase

from core.seguridad_login import esta_bloqueado, registrar_intento


class LimiteIntentosTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_cinco_fallos_bloquean(self):
        for _ in range(5):
            registrar_intento('usuario.prueba', '10.0.0.5', correcto=False)
        self.assertTrue(esta_bloqueado('usuario.prueba', '10.0.0.5'))

    def test_acierto_resetea_el_contador(self):
        registrar_intento('usuario.prueba', '10.0.0.5', correcto=False)
        registrar_intento('usuario.prueba', '10.0.0.5', correcto=True)
        self.assertFalse(esta_bloqueado('usuario.prueba', '10.0.0.5'))
