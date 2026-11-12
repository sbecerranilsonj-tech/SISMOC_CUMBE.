from datetime import date, datetime, time, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from core.models import Usuario
from asistencia.models import Trabajador, IdentidadBiometrica, MarcacionBiometrica, ResumenAsistenciaDiaria, TurnoHorario, IncidenciaAsistencia, AjusteAsistencia, CierreAsistencia, RevisionAsistencia


class AprobacionMasivaTests(TestCase):
    def setUp(self):
        self.contadora = Usuario.objects.create_user('contadora_lote', email='contadora@example.invalid', dni='11111111', rol='CONTADORA')
        self.ficha = Trabajador.objects.create(nombre_completo='Jorge Aguilar', dni='87654321', area='Boletería', sede='CAJAMARCA')
        identidad = IdentidadBiometrica.objects.create(sede='CAJAMARCA', equipo='1', codigo='13', trabajador=self.ficha)
        turno = TurnoHorario.objects.create(nombre='Horario de ocho horas', hora_entrada=time(8), hora_salida=time(17), hora_inicio_refrigerio=time(12), hora_fin_refrigerio=time(13))
        self.desde = date(2026, 8, 1)
        self.hasta = self.desde + timedelta(days=1)
        self.jornadas = []
        for dia in [self.desde, self.hasta]:
            self.jornadas.append(ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha, fecha=dia, primera_entrada=time(8), ultima_salida=time(17), turno_aplicado=turno, horas_trabajadas=8))
            for hora, tipo in [(time(8), 'ENTRADA'), (time(12), 'SALIDA_REFRIGERIO'), (time(13), 'RETORNO_REFRIGERIO'), (time(17), 'SALIDA')]:
                MarcacionBiometrica.objects.create(identidad_biometrica=identidad, fecha_hora=timezone.make_aware(datetime.combine(dia, hora)), tipo_evento=tipo, origen='EXCEL_ZKTECO')
        self.client.force_login(self.contadora)
        self.url = reverse('aprobar_periodo_trabajador')
        self.datos = {'persona_dni': self.ficha.dni, 'desde': str(self.desde), 'hasta': str(self.hasta), 'confirmar_aprobacion': 'si'}

    def test_muestra_validacion_sin_confundir_con_aprobacion(self):
        respuesta = self.client.get(reverse('dashboard'), {'vista': 'asistencia', 'desde': str(self.desde), 'hasta': str(self.hasta), 'persona_dni': self.ficha.dni})
        fila = respuesta.context['pagina_trabajadores'][0]
        self.assertEqual(fila['validadas'], 2)
        self.assertEqual(fila['aprobadas'], 0)
        self.assertEqual(fila['por_aprobar'], 2)
        self.assertEqual(respuesta.context['revision_trabajador']['listas_para_aprobar'], 2)
        self.assertContains(respuesta, 'Aprobación contable')
        self.assertContains(respuesta, 'Aprobar todas las jornadas listas')
        self.assertEqual(ResumenAsistenciaDiaria.objects.filter(verificado_contabilidad=True).count(), 0)

    def test_aprueba_todas_las_listas_con_historial_y_sin_duplicar(self):
        respuesta = self.client.post(self.url, self.datos)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(ResumenAsistenciaDiaria.objects.filter(verificado_contabilidad=True, revisado_por=self.contadora).count(), 2)
        self.assertEqual(RevisionAsistencia.objects.filter(accion='Jornada aprobada').count(), 2)
        self.client.post(self.url, self.datos)
        self.assertEqual(RevisionAsistencia.objects.filter(accion='Jornada aprobada').count(), 2)
        self.assertEqual(self.client.session['resultado_aprobacion_masiva']['ya_aprobadas'], 2)
        self.assertEqual(MarcacionBiometrica.objects.count(), 8)

    def test_deja_incompletas_y_fechas_sin_registrar_con_motivos(self):
        MarcacionBiometrica.objects.filter(fecha_hora__date=self.hasta, tipo_evento='SALIDA').update(tipo_evento='SIN_CLASIFICAR')
        respuesta = self.client.post(self.url, {**self.datos, 'hasta': str(self.hasta + timedelta(days=1))})
        resultado = self.client.session['resultado_aprobacion_masiva']
        self.assertEqual(resultado['aprobadas'], 1)
        self.assertEqual([fila['fecha'] for fila in resultado['pendientes']], [str(self.hasta), str(self.hasta + timedelta(days=1))])
        self.assertIn('marcaciones', ' '.join(resultado['pendientes'][0]['motivos']))
        self.assertEqual(ResumenAsistenciaDiaria.objects.count(), 2)
        self.jornadas[1].refresh_from_db()
        self.assertFalse(self.jornadas[1].verificado_contabilidad)
        pagina = self.client.get(respuesta.url)
        self.assertContains(pagina, 'Resultado de la última aprobación conjunta')
        self.assertEqual(pagina.context['pagina_trabajadores'][0]['validadas'], 1)

    def test_no_aprueba_ajustes_pendientes_ni_jornadas_observadas(self):
        AjusteAsistencia.objects.create(resumen=self.jornadas[0], concepto='horas_extras_25', minutos=15, motivo='Por comprobar', creado_por=self.contadora)
        self.jornadas[1].estado_revision = 'OBSERVADO'
        self.jornadas[1].save(update_fields=['estado_revision'])
        self.client.post(self.url, self.datos)
        self.assertFalse(ResumenAsistenciaDiaria.objects.filter(verificado_contabilidad=True).exists())
        motivos = ' '.join(m for fila in self.client.session['resultado_aprobacion_masiva']['pendientes'] for m in fila['motivos'])
        self.assertIn('ajustes pendientes', motivos)
        self.assertIn('observada', motivos)

    def test_descanso_exige_seleccionar_situacion_individualmente(self):
        dia = self.hasta + timedelta(days=1)
        descanso = ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha, fecha=dia, estado='DIA_LIBRE', horas_trabajadas=0)
        IncidenciaAsistencia.objects.create(resumen=descanso, tipo='DESCANSO_SEMANAL', motivo='Descanso programado', creado_por=self.contadora, aprobado_por=self.contadora, aprobado_el=timezone.now())
        self.client.post(self.url, {**self.datos, 'hasta': str(dia)})
        descanso.refresh_from_db()
        self.assertFalse(descanso.verificado_contabilidad)
        self.assertEqual(self.client.session['resultado_aprobacion_masiva']['aprobadas'], 2)
        self.assertIn('Seleccione la situación', str(self.client.session['resultado_aprobacion_masiva']['pendientes']))

    def test_respeta_cierre_y_no_modifica_jornadas_ajenas_al_periodo(self):
        CierreAsistencia.objects.create(fecha_inicio=self.desde, fecha_fin=self.desde, total_jornadas=1)
        self.client.post(self.url, self.datos)
        self.jornadas[0].refresh_from_db()
        self.jornadas[1].refresh_from_db()
        self.assertFalse(self.jornadas[0].verificado_contabilidad)
        self.assertTrue(self.jornadas[1].verificado_contabilidad)
        self.assertIn('cerrado', ' '.join(self.client.session['resultado_aprobacion_masiva']['pendientes'][0]['motivos']))

    def test_requiere_confirmacion_permiso_y_csrf(self):
        self.client.post(self.url, {**self.datos, 'confirmar_aprobacion': ''})
        self.assertFalse(ResumenAsistenciaDiaria.objects.filter(verificado_contabilidad=True).exists())
        seguro = Client(enforce_csrf_checks=True)
        seguro.force_login(self.contadora)
        self.assertEqual(seguro.post(self.url, self.datos).status_code, 403)
        admin = Usuario.objects.create_user('admin_sin_aprobacion', email='admin@example.invalid', dni='22222222', rol='ADMINISTRADOR')
        self.client.force_login(admin)
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 403)
