"""El endpoint del huellero no acepta IP/Puerto del llamante."""
from unittest.mock import patch

from django.test import TestCase

from asistencia.api import sincronizar_huellero_en_tiempo_real


class HuelleroSinParametrosTests(TestCase):
    @patch('asistencia.api.ZKTecoLiveClient')
    def test_ip_y_puerto_del_llamante_se_ignoran(self, cliente):
        cliente.return_value.sincronizar_marcaciones_en_vivo.return_value = {
            'registros': [], 'total': 0,
        }
        sincronizar_huellero_en_tiempo_real(None, ip='10.0.0.1', puerto=22)
        cliente.assert_called_once_with()
