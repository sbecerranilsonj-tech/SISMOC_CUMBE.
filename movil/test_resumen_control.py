from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import Client, SimpleTestCase, TestCase

from .resumen_control import resumen_web


class ResumenControlTests(SimpleTestCase):
    @patch('movil.resumen_control.calendario')
    def test_muestra_el_mismo_calculo_del_calendario_web(self, calendario):
        calendario.return_value = ([], [{
            'conductor': SimpleNamespace(pk=3),
            'trayectos': 3, 'vueltas': Decimal('1.5'),
            'pago_vueltas': Decimal('30.00'),
            'horas': 1, 'una_x': 1, 'dos_x': 0,
        }])
        resumen = resumen_web(3, date(2026, 8, 1), date(2026, 8, 31))
        self.assertEqual(resumen, {
            'trayectos_realizados': 3, 'vueltas': 1.5, 'estimado': 30,
            'HORA': 1, 'X': 1, 'XX': 0,
        })
        self.assertNotIn('pagado', resumen)

    @patch('movil.resumen_control.calendario')
    def test_conductor_sin_actividad_muestra_ceros(self, calendario):
        calendario.return_value = ([], [])
        self.assertEqual(resumen_web(3, date(2026, 8, 1), date(2026, 8, 31))['trayectos_realizados'], 0)


class ApiTokenSinCsrfTests(TestCase):
    def test_peticion_sin_token_rechazada_por_autenticacion_no_por_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        respuesta = cliente.post('/movil/api/inicio/', data='{}', content_type='application/json')
        self.assertEqual(respuesta.status_code, 401)
        self.assertIn('token', respuesta.json()['error'])
