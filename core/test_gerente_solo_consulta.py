from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from asistencia.models import Trabajador, ResumenAsistenciaDiaria
from asistencia.services.revision import puede_aprobar, puede_gestionar
from core.models import Usuario
from core.security import create_access_token, auth_contadora_or_admin
from movil.models import Perfil, Sesion, Auditoria, Solicitud
from movil.views import hash_token


class GerenteSoloConsultaTests(TestCase):
    def setUp(self):
        self.gerente = Usuario.objects.create_user(
            'gerente-lectura', dni='67676767', rol='GERENTE_GENERAL')
        self.contadora = Usuario.objects.create_user(
            'contadora-edicion', dni='68686868', rol='CONTADORA')
        self.trabajador = Trabajador.objects.create(
            nombre_completo='Trabajador de otra cuenta', dni='69696969',
            sede='CHICLAYO', area='VENTAS')
        self.resumen = ResumenAsistenciaDiaria.objects.create(
            trabajador=self.trabajador, fecha=date(2026, 11, 1))
        self.client.force_login(self.gerente)

    def test_consulta_global_sin_permiso_para_aprobar(self):
        self.assertTrue(puede_gestionar(self.gerente))
        self.assertFalse(puede_aprobar(self.gerente))
        self.assertTrue(puede_aprobar(self.contadora))
        respuesta = self.client.get(reverse('dashboard'), {
            'vista': 'asistencia', 'desde': '2026-11-01', 'hasta': '2026-11-30'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Trabajador de')
        self.assertContains(respuesta, 'Solo consulta')
        self.assertContains(respuesta, 'solo_consulta.js')
        self.assertContains(respuesta, 'Descargar Excel')
        self.assertTrue(respuesta.context['solo_consulta'])
        self.assertFalse(respuesta.context['puede_aprobar'])

    def test_puede_abrir_modulos_y_filtros(self):
        rutas = [
            ('dashboard', {'vista': 'personal'}),
            ('dashboard', {'vista': 'huellero'}),
            ('dashboard', {'vista': 'excel-zk'}),
            ('bancos_control', {}), ('bancos_importar', {}),
            ('conductores_control', {}), ('conductores_importar', {}),
            ('conductores_catalogo', {}), ('movil_panel', {}),
            ('movil_buses', {}), ('programar_horarios', {}),
            ('reglas_jornada', {}),
        ]
        for nombre, consulta in rutas:
            with self.subTest(nombre=nombre, consulta=consulta):
                respuesta = self.client.get(reverse(nombre), consulta)
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(respuesta.context['solo_consulta'])

    def test_escrituras_web_bloqueadas_antes_de_ejecutar_vistas(self):
        rutas = [
            reverse('accion_jornada', args=[self.resumen.pk]),
            reverse('guardar_personal', args=[self.trabajador.pk]),
            reverse('editar_ficha_trabajador', args=[self.trabajador.pk]),
            reverse('aprobar_periodo_trabajador'),
            reverse('validar_marcaciones_trabajador'),
            reverse('registrar_dia_sin_marcas'), reverse('cerrar_periodo'),
            reverse('crear_jornada'), reverse('importar_excel_web'),
            reverse('consultar_huellero'), reverse('agente_prueba_web'),
            reverse('programar_horarios'), reverse('reglas_jornada'),
            reverse('bancos_importar'), reverse('bancos_detalle', args=[999]),
            reverse('conductores_importar'),
            reverse('conductores_detalle', args=[999]),
            reverse('conductores_situacion_dia'),
            reverse('conductores_autorizar_descanso_inicial'),
            reverse('movil_panel'), reverse('movil_buses'),
            reverse('movil_revisar_marca_diaria', args=[self.resumen.pk]),
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                respuesta = self.client.post(ruta, {'accion': 'aprobar'})
                self.assertEqual(respuesta.status_code, 403)
                self.assertIn('solo consulta', respuesta.json()['error'])
        self.resumen.refresh_from_db()
        self.assertFalse(self.resumen.verificado_contabilidad)
        self.assertEqual(Auditoria.objects.count(), 0)
        self.assertEqual(Solicitud.objects.count(), 0)

    def test_tampoco_put_patch_delete_ni_superusuario(self):
        self.gerente.is_staff = self.gerente.is_superuser = True
        self.gerente.save()
        for metodo in ('put', 'patch', 'delete'):
            respuesta = getattr(self.client, metodo)(
                reverse('guardar_personal', args=[self.trabajador.pk]),
                data='{}', content_type='application/json')
            self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(puede_aprobar(self.gerente))

    def test_descarga_excel_permitida(self):
        respuesta = self.client.get(reverse('exportar_asistencia'), {
            'desde': '2026-11-01', 'hasta': '2026-11-30'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('spreadsheetml', respuesta['Content-Type'])

    def test_huellero_consulta_local_sin_sincronizar(self):
        from asistencia.api import consultar_asistencia_tiempo_real
        request = RequestFactory().get('/api/asistencia/tiempo-real')
        request.auth = self.gerente
        with patch('asistencia.api.ZKTecoLiveClient') as cliente:
            cliente.return_value.consultar_registros_locales.return_value = {'registros': []}
            self.assertEqual(consultar_asistencia_tiempo_real(request), {'registros': []})
            cliente.return_value.sincronizar_marcaciones_en_vivo.assert_not_called()
        respuesta = self.client.get(reverse('dashboard'), {'vista': 'huellero'})
        self.assertNotContains(respuesta, 'onclick="abrirConfigHuellero()"')
        self.assertNotContains(respuesta, 'Registrar marcación manual</button>')

    def test_contadora_conserva_escrituras(self):
        self.client.force_login(self.contadora)
        with patch('movil.panel.gestionar') as gestionar:
            respuesta = self.client.post(reverse('movil_panel'), {'accion': 'accion_invalida'})
        # El bloqueo global no se aplica a Contabilidad (la vista valida su acción).
        self.assertNotEqual(respuesta.status_code, 403)

    def test_api_jwt_no_permite_escrituras_sin_sesion_web(self):
        from ninja.errors import HttpError
        token = create_access_token(self.gerente)
        request = RequestFactory().put(
            f'/api/asistencia/verificar-resumen/{self.resumen.pk}',
            data='{}', content_type='application/json')
        with self.assertRaises(HttpError) as error:
            auth_contadora_or_admin.authenticate(request, token)
        self.assertEqual(error.exception.status_code, 403)
        request.method = 'GET'
        self.assertEqual(auth_contadora_or_admin.authenticate(request, token), self.gerente)
        self.resumen.refresh_from_db()
        self.assertFalse(self.resumen.verificado_contabilidad)

    def test_api_movil_solo_admite_consulta(self):
        self.client.logout()
        perfil = Perfil.objects.create(usuario=self.gerente)
        Sesion.objects.create(
            perfil=perfil, token_hash=hash_token('token-gerente-lectura'),
            vence=timezone.now()+timedelta(hours=1))
        for accion in ('solicitud', 'marcar', 'gestionar', 'evento', 'accion_desconocida'):
            respuesta = self.client.post(
                reverse('movil_api', args=[accion]),
                data='{}', content_type='application/json',
                HTTP_AUTHORIZATION='Bearer token-gerente-lectura')
            self.assertEqual(respuesta.status_code, 403)
        respuesta = self.client.post(
            reverse('movil_api', args=['asistencia_periodo']),
            data='{"mes":"2026-11"}', content_type='application/json',
            HTTP_AUTHORIZATION='Bearer token-gerente-lectura')
        self.assertEqual(respuesta.status_code, 200)

    def test_cierre_de_sesion_sigue_permitido(self):
        respuesta = self.client.post(reverse('logout'))
        self.assertEqual(respuesta.status_code, 302)
