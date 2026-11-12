from datetime import date
from urllib.parse import parse_qs, urlparse

from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

from asistencia.models import ResumenAsistenciaDiaria, Trabajador
from asistencia.views import reporte_filtrado, volver
from core.models import Usuario


class FiltroAreaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(
            'admin_areas', email='areas@example.invalid', dni='10000001', rol='ADMINISTRADOR',
        )
        cls.legacy = Usuario.objects.create_user('sin_ficha', email='sin-ficha@example.invalid', dni='10000002')
        cls.ventas = Trabajador.objects.create(
            nombre_completo='Ana Ventas', dni='20000001', area='Ventas', sede='Chiclayo',
        )
        cls.contabilidad = Trabajador.objects.create(
            nombre_completo='Juan Contabilidad', dni='20000002', area='Contabilidad', sede='Chiclayo',
        )
        cls.dia = date(2026, 10, 1)
        for ficha in [cls.ventas, cls.contabilidad]:
            ResumenAsistenciaDiaria.objects.create(trabajador=ficha, fecha=cls.dia)
        ResumenAsistenciaDiaria.objects.create(usuario=cls.legacy, fecha=cls.dia)

    def consultar(self, **filtros):
        request = RequestFactory().get('/', {
            'desde': self.dia.isoformat(), 'hasta': self.dia.isoformat(), **filtros,
        })
        request.user = self.admin
        return reporte_filtrado(request)

    def test_area_filtra_fichas_y_combina_busqueda(self):
        filtros, jornadas = self.consultar(area='Ventas', trabajador='Ana', sede='Chiclayo')
        self.assertEqual(filtros['area'], 'Ventas')
        self.assertEqual(list(jornadas.values_list('trabajador_id', flat=True)), [self.ventas.pk])
        self.assertFalse(self.consultar(area='Ventas', trabajador='Juan')[1].exists())
        self.assertEqual(self.consultar()[1].count(), 3)

    def test_area_sin_completar_incluye_usuario_sin_ficha(self):
        self.assertEqual(list(self.consultar(area='Por completar')[1].values_list('usuario_id', flat=True)), [self.legacy.pk])

    def test_panel_y_retorno_conservan_area(self):
        filtros, _ = self.consultar(area='Ventas')
        html = render_to_string('asistencia/panel.html', {
            'filtros': filtros, 'areas_asistencia': ['Contabilidad', 'Ventas'],
        })
        self.assertIn('name="area"', html)
        self.assertIn('value="Ventas" selected', html)
        self.assertNotIn('name="estado"', html)
        request = RequestFactory().post('/', filtros)
        self.assertEqual(parse_qs(urlparse(volver(request).url).query)['area'], ['Ventas'])
