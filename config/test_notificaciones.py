from datetime import date

from django.test import TestCase
from django.urls import reverse

from core.models import Usuario
from movil.models import Perfil, Solicitud


class NotificacionesSolicitudesTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            'contadora-notificaciones', email='notif@example.invalid',
            dni='55667788', rol='CONTADORA')
        self.client.force_login(self.usuario)

    def test_timbre_de_la_barra_muestra_solicitudes_pendientes(self):
        perfil = Perfil.objects.create(usuario=self.usuario)
        Solicitud.objects.create(
            perfil=perfil, tipo='PERMISO', desde=date(2026, 11, 26),
            hasta=date(2026, 11, 27), detalle='Permiso por asunto personal')
        respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['solicitudes_notificacion']), 1)
        self.assertContains(respuesta, 'class="top-notificaciones"')
        self.assertContains(respuesta, 'Solicitudes pendientes')
        self.assertContains(respuesta, '?solicitud=')
        self.assertContains(respuesta, 'Permiso por asunto personal')

    def test_menu_lateral_sin_usuarios_ni_enlaces_tecnicos(self):
        respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.status_code, 200)
        for texto in ('Usuarios y permisos', 'Enlaces Técnicos',
                      'Swagger API Docs', 'Django Admin'):
            self.assertNotContains(respuesta, texto)

    def test_personal_visible_en_menu_fuera_de_asistencia(self):
        for vista in ('dashboard', 'bancos_control', 'movil_panel'):
            with self.subTest(vista=vista):
                respuesta = self.client.get(reverse(vista))
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, '<span>Personal y jornadas</span>')

    def test_formularios_del_panel_estan_alineados(self):
        respuesta = self.client.get(reverse('movil_panel'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'movil-comision-form')
        self.assertContains(respuesta, 'grid-template-columns:minmax(240px')
        self.assertContains(respuesta, 'Habilitar acceso y generar código')
        self.assertContains(respuesta, 'Comisiones registradas')
        self.assertContains(respuesta, 'data-comisiones-dialog')
        self.assertNotContains(respuesta, 'movil-bell')
        self.assertContains(respuesta, '<th>Función en la app</th>', count=2)
        self.assertContains(respuesta, 'movil-cuentas-dialog')
        self.assertContains(respuesta, 'max-height:92vh!important')

    def test_sin_pendientes_el_timbre_muestra_cero(self):
        respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.context['solicitudes_notificacion'], [])
        self.assertContains(respuesta, 'class="top-notificaciones"')
        self.assertContains(respuesta, 'Sin solicitudes pendientes.')

    def test_empleado_no_ve_solicitudes_ajenas(self):
        perfil = Perfil.objects.create(usuario=self.usuario)
        Solicitud.objects.create(
            perfil=perfil, tipo='VACACIONES', desde=date(2026, 12, 1),
            hasta=date(2026, 12, 5), detalle='Vacaciones')
        otro = Usuario.objects.create_user(
            'empleado-notificaciones', email='empleado@example.invalid',
            dni='99887766', rol='ADMINISTRATIVO')
        self.client.force_login(otro)
        respuesta = self.client.get(reverse('dashboard'))
        self.assertEqual(respuesta.context['solicitudes_notificacion'], [])
        self.assertNotContains(respuesta, 'class="top-notificaciones"')
        self.assertNotContains(respuesta, '<span>Personal y jornadas</span>')
