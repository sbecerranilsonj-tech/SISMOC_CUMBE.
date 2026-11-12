from datetime import datetime, timedelta
from types import SimpleNamespace
from django.test import SimpleTestCase
from asistencia.services.tiempo_faltante import agregar_tiempo_faltante


class TiempoFaltanteTests(SimpleTestCase):
    def test_acumula_deficit_sin_restar_extras_ni_inventar_ausencias(self):
        persona = SimpleNamespace(dni='12345678')
        fila = {'usuario': persona}
        def detalle(segundos, completa=True, situacion=False):
            inicio = datetime(2026,8,1,8)
            return {'resumen':SimpleNamespace(persona=persona), 'completa':completa,
                'solo_situacion':situacion, 'ausencia_justificada':False,
                'tramos':[{'inicio':inicio,'fin':inicio+timedelta(seconds=segundos)}]}
        total = agregar_tiempo_faltante([fila], [detalle(7*3600+50*60+12),
            detalle(7*3600), detalle(10*3600), detalle(0,False), detalle(0,False,True)])
        self.assertEqual(total,'01:09:48')
        self.assertEqual(fila['tiempo_faltante'],'01:09:48')
        self.assertEqual(fila['faltante_por_revisar'],1)

    def test_base_por_revisar_no_interrumpe_resumen(self):
        from unittest.mock import patch
        persona=SimpleNamespace(dni='12345678')
        fila={'usuario':persona}
        d={'resumen':SimpleNamespace(persona=persona),'completa':True,'solo_situacion':False,'ausencia_justificada':False,'tramos':[]}
        with patch('asistencia.services.tiempo_faltante.base_jornada_segundos',return_value=None):
            total=agregar_tiempo_faltante([fila],[d])
        self.assertEqual(total,'00:00:00')
        self.assertEqual(fila['faltante_por_revisar'],1)
