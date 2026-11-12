import csv
import io
from datetime import date, datetime
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from core.models import Usuario
from asistencia.models import Trabajador, IdentidadBiometrica, MarcacionBiometrica, CargaArchivoAsistencia, ResumenAsistenciaDiaria


class AjustesInterfazTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user('ajustes_ui', email='ajustes@example.test', dni='90909090', rol='CONTADORA')
        self.client.force_login(self.admin)
        self.trabajador = Trabajador.objects.create(nombre_completo='Persona Ejemplo', dni='81818181', sede='CHICLAYO')
        self.identidad = IdentidadBiometrica.objects.create(codigo='0013', sede='CHICLAYO', equipo='104', trabajador=self.trabajador)
        self.carga = CargaArchivoAsistencia.objects.create(nombre_archivo_original='prueba.xls', subido_por=self.admin, estado='COMPLETADO')
        MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad, carga_origen=self.carga, fecha_hora=timezone.make_aware(datetime(2026,8,1,8)))

    def test_exportacion_codigo_y_columnas_solicitadas(self):
        ResumenAsistenciaDiaria.objects.create(trabajador=self.trabajador, fecha=date(2026,8,1))
        response = self.client.get(reverse('exportar_asistencia'), {'desde':'2026-08-01','hasta':'2026-08-01'})
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(rows[0], ['Desde','Hasta','Código','Trabajador','Sede','Jornadas','Horas efectivas','Extras 25 %','Extras 35 %','Nocturnas','Descanso/feriado','Tiempo faltante (HH:MM:SS)','Aprobadas','Pendientes'])
        self.assertEqual(rows[1][2], '0013')
        self.assertNotIn(self.trabajador.dni, rows[1])
        self.assertEqual(len(rows[0]), len(rows[1]))

    def test_importador_carga_datos_al_entrar_y_navegacion_consulta_servidor(self):
        response = self.client.get(reverse('dashboard'), {'vista':'excel-zk'})
        self.assertEqual(list(response.context['identidades_biometricas']), [self.identidad])
        self.assertContains(response, '0013')
        self.assertContains(response, "['personal', 'excel-zk'].includes(seccionId)")

    def test_fechas_arriba_y_programacion_en_popup(self):
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'dashboard-top-row')
        self.assertNotContains(response, 'Filtros del periodo')
        response = self.client.get(reverse('dashboard'), {'vista':'personal'})
        self.assertContains(response, 'data-rule-popup="Programar horarios"')

    def test_horarios_puede_mostrarse_en_popup_del_mismo_sistema(self):
        response=self.client.get(reverse('programar_horarios'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers.get('X-Frame-Options'), 'SAMEORIGIN')
        response=self.client.get(reverse('dashboard'))
        self.assertNotContains(response, '<li class="menu-category">Planificación IQ2</li>')
        self.assertNotContains(response, '<span>Prototipos Sprints 02 a 04</span>')
