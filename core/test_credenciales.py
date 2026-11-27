"""Cada usuario puede cambiar su propio usuario y contraseña."""
from django.test import TestCase
from django.urls import reverse

from core.models import Usuario


class CambioDeCredencialesTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            'contadora.prueba', dni='85858585', rol='CONTADORA',
            password='ClaveActual2026!')
        self.otro = Usuario.objects.create_user(
            'ocupado', dni='86868686', rol='BOLETERIA',
            password='OtraClave2026!')
        self.client.force_login(self.usuario)
        self.url = reverse('cambiar_credenciales')

    def test_formulario_disponible_para_el_usuario(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Contraseña actual')
        self.assertContains(respuesta, 'Nuevo usuario')

    def test_requiere_clave_actual_y_no_cambia_nada_si_falla(self):
        respuesta = self.client.post(self.url, {
            'actual': 'incorrecta', 'username': 'nuevo.nombre',
            'password': 'ClaveNueva2026!', 'password2': 'ClaveNueva2026!'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'contraseña actual no es correcta')
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'contadora.prueba')
        self.assertTrue(self.usuario.check_password('ClaveActual2026!'))

    def test_cambia_usuario_y_contraseña_conservando_la_sesion(self):
        respuesta = self.client.post(self.url, {
            'actual': 'ClaveActual2026!', 'username': 'contadora.nueva',
            'password': 'ClaveNueva2026!', 'password2': 'ClaveNueva2026!'})
        self.assertEqual(respuesta.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.username, 'contadora.nueva')
        self.assertTrue(self.usuario.check_password('ClaveNueva2026!'))
        self.assertEqual(self.usuario.rol, 'CONTADORA')
        self.assertFalse(self.usuario.is_staff)
        self.assertFalse(self.usuario.is_superuser)
        # La sesión sigue autenticada tras update_session_auth_hash.
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_no_permite_usuario_ya_registrado_ni_claves_distintas(self):
        respuesta = self.client.post(self.url, {
            'actual': 'ClaveActual2026!', 'username': 'ocupado',
            'password': '', 'password2': ''})
        self.assertContains(respuesta, 'ya está registrado')
        respuesta = self.client.post(self.url, {
            'actual': 'ClaveActual2026!', 'username': 'contadora.prueba',
            'password': 'ClaveUno2026!', 'password2': 'ClaveDos2026!'})
        self.assertContains(respuesta, 'no coinciden')
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('ClaveActual2026!'))

    def test_solo_usuario_autenticado(self):
        self.client.logout()
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta['Location'])
