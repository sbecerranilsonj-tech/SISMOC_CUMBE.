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
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb['Resumen de asistencia']
        self.assertEqual(ws['A9'].value, 'Código importado')
        self.assertEqual(ws['A10'].value, '0013')
        self.assertEqual(ws['A10'].data_type, 's')
        self.assertNotIn(self.trabajador.dni, [cell.value for row in ws for cell in row])
        self.assertEqual(wb.sheetnames, ['Resumen de asistencia', 'Detalle diario'])

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
