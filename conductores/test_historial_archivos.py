from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from core.models import Usuario
from .models import Importacion, Salida


class HistorialArchivosTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            'historial-excel', email='historial@example.invalid',
            dni='66778899', rol='CONTADORA')
        self.client.force_login(self.usuario)
        self.lotes = []
        for indice, archivo in enumerate(('', 'itinerarios/reporte.xlsx')):
            lote = Importacion.objects.create(
                nombre='Programación manual · sin Excel' if not archivo else 'reporte.xlsx',
                huella=str(indice) * 64, archivo=archivo, estado='VALIDADO',
                inicio=date(2026, 11, 27), fin=date(2026, 11, 27),
                creado_por=self.usuario)
            Salida.objects.create(
                importacion=lote, fila=1, fecha=lote.inicio, hora=time(10),
                bus='BUS', origen='CHICLAYO', destino='JAEN')
            self.lotes.append(lote)

    def test_historial_solo_muestra_excel_sin_eliminar_programaciones(self):
        respuesta = self.client.get(reverse('conductores_importar'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'Programación manual · sin Excel')
        self.assertContains(respuesta, 'reporte.xlsx')
        self.assertContains(respuesta, 'data-abrir-reportes')
        self.assertContains(respuesta, '<dialog id="reportes-itinerarios-dialog"')
        self.assertContains(respuesta, 'data-cerrar-reportes')
        self.assertContains(respuesta, 'Descargar original')
        self.assertEqual([l.pk for l in respuesta.context['lotes']], [self.lotes[1].pk])
        self.assertEqual(respuesta.context['total_registros'], 1)
        self.assertEqual(Salida.objects.count(), 2)
        self.assertEqual(Importacion.objects.count(), 2)

    def test_filtro_manual_no_lo_reintroduce_en_el_historial(self):
        respuesta = self.client.get(
            reverse('conductores_importar'), {'archivo': self.lotes[0].pk})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['lotes'], [])
        self.assertEqual(respuesta.context['total_salidas'], 0)
