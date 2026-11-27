"""Verifica que los prototipos sean de lectura y no requieran registros reales."""
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from core.views_prototipos import prototipos_iq2


class PrototiposIQ2Tests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_exige_sesion(self):
        request = self.factory.get(reverse("prototipos_iq2"))
        request.user = AnonymousUser()
        response = prototipos_iq2(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_renderiza_sin_consultar_datos_reales(self):
        # SimpleTestCase rechaza cualquier consulta a la base de datos.
        request = self.factory.get(reverse("prototipos_iq2"))
        request.user = SimpleNamespace(is_authenticated=True)
        response = prototipos_iq2(request)
        self.assertContains(response, "Datos ficticios")
        self.assertContains(response, 'data-view="conciliacion"')
        self.assertContains(response, 'data-view="asistencia"')
        self.assertContains(response, 'data-view="rutas"')
        self.assertContains(response, 'data-view="croquis"')
        self.assertContains(response, 'data-view="kanban"')

    def test_rechaza_escrituras(self):
        request = self.factory.post(reverse("prototipos_iq2"), {"accion": "guardar"})
        request.user = SimpleNamespace(is_authenticated=True)
        self.assertEqual(prototipos_iq2(request).status_code, 405)
