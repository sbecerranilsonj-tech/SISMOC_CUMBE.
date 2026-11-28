"""El bloqueo de login empieza en 5 minutos y aumenta por niveles."""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from core.seguridad_login import (
    esta_bloqueado, registrar_intento, segundos_de_espera, minutos_de_espera,
)


class LimiteIntentosTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_cuatro_fallos_no_bloquean(self):
        for _ in range(4):
            registrar_intento('usuario.prueba', '10.0.0.5', correcto=False)
        self.assertFalse(esta_bloqueado('usuario.prueba', '10.0.0.5'))

    def test_cinco_fallos_bloquean(self):
        for _ in range(5):
            registrar_intento('usuario.prueba', '10.0.0.5', correcto=False)
        self.assertTrue(esta_bloqueado('usuario.prueba', '10.0.0.5'))

    def test_espera_escalona_y_tiene_tope(self):
        self.assertEqual(segundos_de_espera(5), 300)
        self.assertEqual(segundos_de_espera(9), 300)
        self.assertEqual(segundos_de_espera(10), 600)
        self.assertEqual(segundos_de_espera(15), 1200)
        self.assertEqual(segundos_de_espera(20), 2400)
        self.assertEqual(segundos_de_espera(25), 3600)
        self.assertEqual(segundos_de_espera(40), 3600)

    def test_bloqueo_usa_la_espera_del_nivel(self):
        class CacheFalsa:
            def __init__(self):
                self.datos = {}
                self.esperas = {}

            def get(self, clave, predicado=None):
                return self.datos.get(clave, predicado)

            def set(self, clave, valor,timeout=None):
                self.datos[clave] = valor
                self.esperas[clave] = timeout

            def delete(self, clave):
                self.datos.pop(clave, None)
                self.esperas.pop(clave, None)

        falsa = CacheFalsa()
        with patch('core.seguridad_login.cache', falsa):
            for _ in range(10):
                registrar_intento('usuario.prueba', '10.0.0.5', correcto=False)
        bloqueos = [espera for clave, espera in falsa.esperas.items()
                    if clave.startswith('login_bloqueo:')]
        self.assertEqual(max(bloqueos), 600)

    def test_minutos_mostrados_coinciden_con_el_nivel(self):
        for _ in range(5):
            registrar_intento('usuario.prueba', '10.0.0.5', correcto=False)
        self.assertEqual(minutos_de_espera('usuario.prueba', '10.0.0.5'), 5)
        for _ in range(5):
            registrar_intento('usuario.prueba', '10.0.0.5', correcto=False)
        self.assertEqual(minutos_de_espera('usuario.prueba', '10.0.0.5'), 10)

    def test_acierto_resetea_el_contador_y_el_bloqueo(self):
        for _ in range(5):
            registrar_intento('usuario.prueba', '10.0.0.5', correcto=False)
        self.assertTrue(esta_bloqueado('usuario.prueba', '10.0.0.5'))
        registrar_intento('usuario.prueba', '10.0.0.5', correcto=True)
        self.assertFalse(esta_bloqueado('usuario.prueba', '10.0.0.5'))
