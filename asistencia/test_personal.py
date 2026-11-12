from datetime import date
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from asistencia.models import Trabajador, IdentidadBiometrica, DescansoProgramado, ResumenAsistenciaDiaria
from asistencia.services.reglas_jornada import descanso_previsto
from core.models import Usuario


class PersonalTests(TestCase):
    def setUp(self):
        self.actor = Usuario.objects.create_user('personal_prueba', email='personal@example.invalid', dni='11223344', rol='CONTADORA')
        self.t = Trabajador.objects.create(nombre_completo='Persona de prueba', nombres='María', apellido_paterno='Pérez', dni='22334455', area='VIGILANTE', sede='CHICLAYO')
        self.i = IdentidadBiometrica.objects.create(trabajador=self.t, codigo='100', equipo='1', sede='CHICLAYO')
        self.client.force_login(self.actor)

    def test_listado_y_ficha_sin_crear_jornadas(self):
        r = self.client.get(reverse('dashboard'), {'vista': 'personal', 'ficha': self.t.pk})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Descansos programados')
        self.assertContains(r, 'Horario creado')
        self.assertFalse(ResumenAsistenciaDiaria.objects.exists())

    def test_edita_datos_sin_alterar_codigo(self):
        self.client.post(reverse('guardar_personal', args=[self.t.pk]), {'accion': 'datos', 'nombres': 'María', 'apellido_paterno': 'Pérez', 'apellido_materno': '', 'dni': self.t.dni, 'area': 'TESORERA', 'sede': 'CHICLAYO', 'codigo': 'otro'})
        self.t.refresh_from_db(); self.i.refresh_from_db()
        self.assertEqual(self.t.area, 'TESORERA')
        self.assertEqual(self.i.codigo, '100')

    def test_nocturnas_y_descanso_no_aprueban_dias(self):
        self.client.post(reverse('guardar_personal', args=[self.t.pk]), {'accion': 'nocturnas', 'calcular_nocturnas': 'si'})
        self.t.refresh_from_db(); self.assertTrue(self.t.calcular_nocturnas)
        self.client.post(reverse('guardar_personal', args=[self.t.pk]), {'accion': 'descanso', 'desde': '2026-11-01', 'hasta': '2026-11-30', 'dias': ['5']})
        self.assertEqual(DescansoProgramado.objects.get().dias, [5])
        self.assertFalse(ResumenAsistenciaDiaria.objects.exists())
        resumen = ResumenAsistenciaDiaria(trabajador=self.t, fecha=date(2026,11,7))
        self.assertTrue(descanso_previsto(resumen))
        self.client.post(reverse('guardar_personal', args=[self.t.pk]), {'accion': 'descanso', 'desde': '2026-11-07', 'hasta': '2026-11-07'})
        self.assertFalse(descanso_previsto(resumen))

    def test_permiso_y_vigencia_invalida(self):
        self.client.post(reverse('guardar_personal', args=[self.t.pk]), {'accion': 'descanso', 'desde': '2026-11-30', 'hasta': '2026-11-01', 'dias': ['5']})
        self.assertFalse(DescansoProgramado.objects.exists())
        self.actor.rol = 'TRABAJADOR'; self.actor.save()
        r = self.client.post(reverse('guardar_personal', args=[self.t.pk]), {'accion': 'nocturnas', 'calcular_nocturnas': 'si'})
        self.assertEqual(r.status_code, 403)

    def test_asigna_horario_creado_al_trabajador_de_la_ficha(self):
        from datetime import time
        from asistencia.models import TurnoHorario, ProgramacionHorario
        turno = TurnoHorario.objects.create(nombre='Mañana', hora_entrada=time(6), hora_salida=time(14,30))
        self.client.post(reverse('guardar_personal', args=[self.t.pk]), {
            'accion':'horario', 'horario-trabajador':'999999', 'horario-turno':turno.pk,
            'horario-desde':'2026-11-05', 'horario-hasta':'2026-11-06',
            'horario-dias':['3','4'], 'horario-confirmado':'on',
        })
        self.assertEqual(ProgramacionHorario.objects.filter(trabajador=self.t, turno=turno).count(),2)
        self.assertFalse(ResumenAsistenciaDiaria.objects.exists())

    def test_mensajes_de_guardado_y_error_aparecen_dentro_del_popup(self):
        url = reverse('guardar_personal', args=[self.t.pk])
        for datos, texto in [({'accion': 'nocturnas'}, 'Configuración del trabajador guardada.'), ({'accion': 'horario'}, 'Este campo es obligatorio.')]:
            response = self.client.post(url, datos, follow=True)
            html = response.content.decode()
            inicio = html.index('id="ficha-personal"')
            fin = html.index('</dialog>', inicio)
            self.assertIn('personal-config-feedback', html[inicio:fin])
            self.assertIn(texto, html[inicio:fin])
            self.assertNotIn(texto, html[:inicio])

    def test_dias_trabajo_programan_descanso_complementario(self):
        self.client.post(reverse('guardar_personal', args=[self.t.pk]), {
            'accion': 'dias_laborales', 'desde': '2026-08-01', 'hasta': '2026-08-31', 'dias': ['1', '2', '3']})
        self.assertEqual(DescansoProgramado.objects.get(trabajador=self.t).dias, [0, 4, 5, 6])
        self.assertFalse(ResumenAsistenciaDiaria.objects.exists())

    def test_casillas_extras_independientes_de_nocturnas(self):
        self.t.calcular_nocturnas = True
        self.t.save()
        self.client.post(reverse('guardar_personal', args=[self.t.pk]), {'accion': 'extras', 'calcular_extras_35': 'si'})
        self.t.refresh_from_db()
        self.assertFalse(self.t.calcular_extras_25)
        self.assertTrue(self.t.calcular_extras_35)
        self.assertTrue(self.t.calcular_nocturnas)

    def test_validar_descansos_solo_fechas_programadas_sin_marcas(self):
        from asistencia.services.validacion_descansos import validar_descansos
        from asistencia.models import MarcacionBiometrica
        from datetime import datetime, time
        DescansoProgramado.objects.create(trabajador=self.t, responsable=self.actor, desde=date(2026, 8, 3), hasta=date(2026, 8, 9), dias=[0, 4, 5, 6])
        MarcacionBiometrica.objects.create(identidad_biometrica=self.i, fecha_hora=timezone.make_aware(datetime(2026, 8, 7, 8)), tipo_evento='ENTRADA')
        aprobadas, omitidas = validar_descansos(self.t, date(2026, 8, 3), date(2026, 8, 9), self.actor)
        self.assertEqual(aprobadas, 3)
        self.assertEqual(omitidas, 1)
        self.assertEqual(ResumenAsistenciaDiaria.objects.filter(verificado_contabilidad=True).count(), 3)
        self.assertFalse(ResumenAsistenciaDiaria.objects.filter(fecha=date(2026, 8, 7)).exists())
        for r in ResumenAsistenciaDiaria.objects.all():
            self.assertTrue(r.conceptos_editados['descanso_validado_programacion'])
        self.assertEqual(validar_descansos(self.t, date(2026, 8, 3), date(2026, 8, 9), self.actor)[0], 0)

    def test_validacion_dias_sin_programacion_no_es_descanso_semanal(self):
        from asistencia.services.validacion_descansos import validar_descansos
        DescansoProgramado.objects.create(trabajador=self.t, responsable=self.actor, desde=date(2026, 8, 3), hasta=date(2026, 8, 3), dias=[0], sin_trabajo_programado=True)
        validar_descansos(self.t, date(2026, 8, 3), date(2026, 8, 3), self.actor)
        r = ResumenAsistenciaDiaria.objects.get(trabajador=self.t)
        self.assertEqual(r.incidencias.get().tipo, 'SIN_PROGRAMACION')
        self.assertTrue(r.verificado_contabilidad)

    def test_historial_incluye_configuraciones_y_detalles_solo_del_trabajador(self):
        from asistencia.services.revision import registrar_historial
        registrar_historial(None, self.actor, 'Configuración de extras', f'Trabajador #{self.t.pk}: 25%=False; 35%=True.')
        registrar_historial(None, self.actor, 'Configuración de extras', f'Trabajador #{self.t.pk}0: ajeno.')
        response = self.client.get(reverse('dashboard'), {'vista': 'personal', 'ficha': self.t.pk})
        self.assertContains(response, 'Configuración de extras')
        self.assertContains(response, 'Horas extras al 25 %: desactivadas.')
        self.assertNotContains(response, 'ajeno.')
        self.assertNotContains(response, 'La situación real se confirma en Asistencia.')
