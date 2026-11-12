from datetime import date, datetime, time, timedelta
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.db import connection
from django.test.utils import CaptureQueriesContext
from core.models import Usuario
from asistencia.models import Trabajador, IdentidadBiometrica, MarcacionBiometrica, ResumenAsistenciaDiaria, CierreAsistencia, TurnoHorario
from asistencia.services.transferencia import pasar_a_asistencia
from asistencia.services.revision import detalle_jornada, revisar


class TransferenciaAsistenciaTests(TestCase):
    def setUp(self):
        self.gestor = Usuario.objects.create_user('gestor_envio', email='gestor@example.invalid', dni='11111111', rol='CONTADORA')
        self.ficha = Trabajador.objects.create(nombre_completo='Jorge Aguilar', dni='87654321', area='Boletería', sede='CAJAMARCA')
        self.identidad = IdentidadBiometrica.objects.create(sede='CAJAMARCA', equipo='1', codigo='13', trabajador=self.ficha, nombre=self.ficha.nombre_completo)
        self.dia = date(2026, 8, 1)
        for hora in [time(8), time(12), time(13), time(17)]:
            MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad, fecha_hora=timezone.make_aware(datetime.combine(self.dia, hora)))
        self.client.force_login(self.gestor)

    def enviar(self):
        return pasar_a_asistencia([self.ficha.pk], self.dia, self.dia, self.gestor)

    def test_envia_sin_cuenta_y_no_duplica_ni_inventa_horas(self):
        self.assertEqual(self.enviar()['nuevas'], 1)
        resumen = ResumenAsistenciaDiaria.objects.get()
        self.assertIsNone(resumen.usuario_id)
        self.assertEqual(resumen.trabajador, self.ficha)
        self.assertEqual(resumen.estado, 'POR_REVISAR')
        self.assertFalse(resumen.verificado_contabilidad)
        self.assertEqual(resumen.horas_trabajadas, 0)
        self.assertEqual(len(detalle_jornada(resumen)['marcas']), 4)
        self.assertEqual(detalle_jornada(resumen)['cuadro_excel']['totales']['trabajo'], 'Por revisar')
        self.assertEqual(self.enviar()['existentes'], 1)
        self.assertEqual(ResumenAsistenciaDiaria.objects.count(), 1)
        self.assertEqual(Usuario.objects.count(), 1)

    def test_consulta_filtros_detalle_exportacion_y_api_sin_cuenta(self):
        self.enviar()
        resumen = ResumenAsistenciaDiaria.objects.get()
        filtros = {'vista': 'asistencia', 'desde': str(self.dia), 'hasta': str(self.dia), 'trabajador': 'Aguilar', 'sede': 'CAJAMARCA', 'detalle': resumen.pk}
        respuesta = self.client.get(reverse('dashboard'), filtros)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['total_jornadas'], 1)
        self.assertContains(respuesta, self.ficha.nombre_completo)
        self.assertContains(respuesta, 'Guardar todas las correcciones')
        exportado = self.client.get(reverse('exportar_asistencia'), filtros)
        self.assertContains(exportado, self.identidad.codigo)
        self.assertNotContains(exportado, self.ficha.dni)
        from core.security import create_access_token
        token = create_access_token(self.gestor)
        respuesta = self.client.get('/api/asistencia/resumen', {'fecha_inicio': str(self.dia), 'fecha_fin': str(self.dia), 'dni': self.ficha.dni}, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()[0]['dni'], self.ficha.dni)
        respuesta = self.client.get('/api/asistencia/reporte-planilla', {'fecha_inicio': str(self.dia), 'fecha_fin': str(self.dia)}, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['total_colaboradores'], 1)

    def test_no_envia_ficha_incompleta_ni_periodo_cerrado(self):
        self.ficha.area = 'Por completar'
        self.ficha.save()
        with self.assertRaises(ValidationError): self.enviar()
        self.assertFalse(ResumenAsistenciaDiaria.objects.exists())
        self.ficha.area = 'Ventas'
        self.ficha.save()
        CierreAsistencia.objects.create(fecha_inicio=self.dia, fecha_fin=self.dia, total_jornadas=0)
        with self.assertRaises(ValidationError): self.enviar()
        self.assertFalse(ResumenAsistenciaDiaria.objects.exists())

    def test_boton_respeta_filtros_y_abre_periodo_importado(self):
        respuesta = self.client.get(reverse('dashboard'), {'vista': 'excel-zk'})
        self.assertContains(respuesta, 'Validar y enviar')
        IdentidadBiometrica.objects.create(sede='TRUJILLO', equipo='1', codigo='99')
        respuesta = self.client.post(reverse('enviar_a_asistencia'), {'confirmar_identificacion': 'si', 'desde_envio': str(self.dia), 'hasta_envio': str(self.dia), 'sede_codigo': 'CAJAMARCA'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('desde=2026-08-01', respuesta.url)
        self.assertIn('vista=asistencia', respuesta.url)
        self.assertEqual(ResumenAsistenciaDiaria.objects.count(), 1)

    def test_permisos_y_csrf_envio(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.gestor)
        self.assertEqual(cliente.post(reverse('enviar_a_asistencia')).status_code, 403)
        empleado = Usuario.objects.create_user('sin_permiso_envio', email='empleado@example.invalid', dni='22222222', rol='ADMINISTRATIVO')
        self.client.force_login(empleado)
        self.assertEqual(self.client.post(reverse('enviar_a_asistencia')).status_code, 403)

    def test_clasificacion_y_horario_pueden_revisarse_sin_cuenta(self):
        self.enviar()
        resumen = ResumenAsistenciaDiaria.objects.get()
        turno = TurnoHorario.objects.create(nombre='Horario revisión', hora_entrada=time(8), hora_salida=time(17), hora_inicio_refrigerio=time(12), hora_fin_refrigerio=time(13))
        self.client.post(reverse('accion_jornada', args=[resumen.pk]), {'accion': 'turno', 'turno': turno.pk})
        for marca, tipo in zip(MarcacionBiometrica.objects.order_by('fecha_hora'), ['ENTRADA', 'SALIDA_REFRIGERIO', 'RETORNO_REFRIGERIO', 'SALIDA']):
            self.client.post(reverse('accion_jornada', args=[resumen.pk]), {'accion': 'corregir_evento', 'marcacion_id': marca.pk, 'tipo_evento': tipo, 'motivo': 'Clasificado con evidencia'})
        resumen.refresh_from_db()
        self.assertTrue(detalle_jornada(resumen)['completa'])
        self.assertEqual(detalle_jornada(resumen)['trabajo_reconstruido'], '08:00:00')

    def test_entrada_salida_nocturna_clasificada_no_se_divide(self):
        MarcacionBiometrica.objects.all().delete()
        for dia, hora, tipo in [(self.dia, time(22), 'ENTRADA'), (self.dia + timedelta(days=1), time(6), 'SALIDA')]:
            MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad, fecha_hora=timezone.make_aware(datetime.combine(dia, hora)), tipo_evento=tipo)
        self.enviar()
        self.assertEqual(ResumenAsistenciaDiaria.objects.count(), 1)
        resumen = ResumenAsistenciaDiaria.objects.get()
        self.assertEqual(resumen.horas_trabajadas, 8)
        self.assertEqual(resumen.horas_nocturnas, 8)
        self.assertEqual(detalle_jornada(resumen)['trabajo_reconstruido'], '08:00:00')

    def test_envio_mensual_acota_consultas_y_preserva_aprobaciones(self):
        fin = self.dia + timedelta(days=22)
        MarcacionBiometrica.objects.bulk_create([
            MarcacionBiometrica(identidad_biometrica=self.identidad,
                fecha_hora=timezone.make_aware(datetime.combine(self.dia + timedelta(days=d), h)))
            for d in range(1, 23) for h in [time(8), time(12), time(13), time(17)]
        ])
        with CaptureQueriesContext(connection) as consultas:
            resultado = pasar_a_asistencia([self.ficha.pk], self.dia, fin, self.gestor)
        self.assertEqual(resultado['nuevas'], 23)
        self.assertLess(len(consultas), 30)
        resumen = ResumenAsistenciaDiaria.objects.get(fecha=self.dia)
        resumen.estado_revision = 'APROBADO'
        resumen.verificado_contabilidad = True
        resumen.save()
        from asistencia.models import RevisionAsistencia
        historial = RevisionAsistencia.objects.count()
        self.assertEqual(historial, 23)
        with CaptureQueriesContext(connection) as consultas:
            repetido = pasar_a_asistencia([self.ficha.pk], self.dia, fin, self.gestor)
        self.assertLess(len(consultas), 20)
        self.assertEqual(repetido['nuevas'], 0)
        self.assertEqual(repetido['existentes'], 23)
        resumen.refresh_from_db()
        self.assertTrue(resumen.verificado_contabilidad)
        self.assertEqual(resumen.estado_revision, 'APROBADO')
        self.assertEqual(RevisionAsistencia.objects.count(), historial)
