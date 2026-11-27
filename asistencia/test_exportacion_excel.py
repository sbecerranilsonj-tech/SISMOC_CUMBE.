from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook
from core.models import Usuario
from asistencia.models import (Trabajador, IdentidadBiometrica,
                               ResumenAsistenciaDiaria, MarcacionBiometrica)


class ExportacionExcelTests(TestCase):
    def setUp(self):
        self.gestor = Usuario.objects.create_user('excel_gestor',email='prueba@example.invalid',dni='10101010',rol='CONTADORA')
        self.persona = Trabajador.objects.create(nombre_completo='Persona Ejemplo',dni='20202020',sede='CHICLAYO',area='VENTAS')
        self.identidad = IdentidadBiometrica.objects.create(trabajador=self.persona,codigo='0013',sede='CHICLAYO')
        IdentidadBiometrica.objects.create(trabajador=self.persona,codigo='CUM-PRUEBA',sede='CHICLAYO')
        for dia in range(1,6):
            jornada=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=date(2026,11,dia))
            for hora, tipo in [(datetime(2026,11,dia,8,0),'ENTRADA'),(datetime(2026,11,dia,17,0),'SALIDA')]:
                MarcacionBiometrica.objects.create(
                    dni='20202020', nombre_empleado='Persona Ejemplo', identidad_biometrica=self.identidad,
                    zkteco_user_id=13, fecha_hora=hora, tipo_evento=tipo,
                    origen=MarcacionBiometrica.OrigenMarcacion.ZKTECO_EN_LINEA,
                    dispositivo_ip='192.168.10.202', sede='CHICLAYO')
            ResumenAsistenciaDiaria.objects.filter(pk=jornada.pk).update(horas_trabajadas=Decimal('8.25'),verificado_contabilidad=dia<=3,estado_revision='APROBADO' if dia<=3 else 'PENDIENTE')
        self.client.force_login(self.gestor)
        self.query={'desde':'2026-11-01','hasta':'2026-11-30'}

    def descargar(self, **filtros):
        response=self.client.get(reverse('exportar_asistencia'),{**self.query,**filtros})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response['Content-Disposition'].endswith('.xlsx"'))
        return load_workbook(BytesIO(response.content))

    def test_libro_formateado_datos_y_totales(self):
        wb=self.descargar()
        ws=wb['Resumen de asistencia']
        self.assertEqual(wb.sheetnames[0],'Resumen de asistencia')
        self.assertNotIn('Detalle diario',wb.sheetnames)
        self.assertIn('CHICLAYO',wb.sheetnames)
        self.assertIn('Persona Ejemplo',wb.sheetnames)
        self.assertEqual(ws['A10'].value,'0013')
        self.assertEqual(ws['A10'].data_type,'s')
        self.assertEqual(ws['E10'].value,5)
        self.assertEqual(ws['F10'].value,41.25)
        self.assertEqual(ws['L10'].value,3)
        self.assertEqual(ws['M10'].value,2)
        self.assertEqual(ws.max_column,13)
        self.assertEqual(ws['M9'].value,'Pendientes')
        self.assertNotIn('Observadas',[cell.value for cell in ws[9]])
        self.assertEqual(ws['E11'].value,'=SUM(E10:E10)')
        self.assertEqual(ws['K10'].number_format,'[h]:mm:ss')
        self.assertEqual(ws.freeze_panes,'C10')
        self.assertEqual(ws.auto_filter.ref,'A9:M10')
        self.assertFalse(ws.sheet_view.showGridLines)
        self.assertEqual(ws['A9'].fill.fgColor.rgb[-6:],'173C35')
        self.assertEqual(wb['Persona Ejemplo'].max_row,23)
        self.assertNotIn('CUM-PRUEBA',[cell.value for sheet in wb for row in sheet for cell in row])

    def test_fichas_agrupadas_por_sede_y_trabajador(self):
        wb = self.descargar()
        sede = wb['CHICLAYO']
        self.assertIn('RESUMEN POR SEDE', sede['A2'].value)
        self.assertEqual(sede['E10'].value, 5)
        ficha = wb['Persona Ejemplo']
        self.assertIn('FICHA POR TRABAJADOR', ficha.cell(2, 1).value)
        self.assertEqual(ficha.cell(9, 1).value, '0013')
        self.assertIsInstance(ficha.cell(9, 2).value, datetime)
        self.assertEqual(ficha.cell(10, 4).value, '09:00:00')
        self.assertEqual(ficha.cell(11, 3).value, 'Total trabajado y conceptos del día')
        self.assertEqual(ficha.cell(11, 12).value, 'APROBADO')
        self.assertEqual(ficha.cell(23, 12).value, 'PENDIENTE')
        self.assertEqual(ficha.max_row, 23)
        self.assertFalse(any(' · APROBADO' in str(c.value) or ' · PENDIENTE' in str(c.value)
                             for row in ficha.iter_rows(min_row=9) for c in row))
        self.assertEqual(ficha.cell(8, 8).value, 'HH.EE. 25 %\nPrimeras 2 h')
        from asistencia.services.revision_trabajador import detalles_en_lote
        jornadas = list(ResumenAsistenciaDiaria.objects.filter(trabajador=self.persona).order_by('fecha'))
        cuadro = detalles_en_lote(jornadas)[0]['cuadro_excel']
        for columna, clave in [(6, 'base'), (7, 'saldo'), (8, 'he25'), (9, 'he35'), (10, 'nocturnas')]:
            esperado = cuadro['totales'][clave]
            self.assertEqual(ficha.cell(11, columna).value or '', '' if esperado == 'Por revisar' else esperado)

    def test_filtros_se_aplican_en_ambas_hojas(self):
        wb=self.descargar(revision='APROBADO',sede='CHICLAYO')
        self.assertEqual(wb['Resumen de asistencia']['E10'].value,3)
        self.assertIn('Revisión: APROBADO',wb['Resumen de asistencia']['A4'].value)
        self.assertEqual(wb['Persona Ejemplo'].max_row,17)

    def test_descansos_y_permisos_coloreados_sin_inventar_marcas(self):
        MarcacionBiometrica.objects.all().delete()
        jornadas = ResumenAsistenciaDiaria.objects.filter(trabajador=self.persona)
        jornadas.filter(fecha=date(2026,11,1)).update(estado='DESCANSO_MEDICO')
        jornadas.filter(fecha=date(2026,11,2)).update(estado='PERMISO')
        ficha = self.descargar()['Persona Ejemplo']
        self.assertEqual(ficha['C9'].fill.fgColor.rgb[-6:], 'EDE3F8')
        self.assertEqual(ficha['C11'].fill.fgColor.rgb[-6:], 'DBEAFE')
        self.assertIn(ficha['D11'].value, ('', None))

    def test_vacio_genera_libro_valido(self):
        wb=self.descargar(sede='JAEN')
        self.assertEqual(wb['Resumen de asistencia']['E11'].value,0)
        self.assertIn('No hay jornadas',wb['Resumen de asistencia']['A10'].value)

    def test_valores_externos_son_texto_no_formulas(self):
        IdentidadBiometrica.objects.filter(codigo='0013').update(codigo='=1+1')
        self.persona.nombre_completo='=SUM(A1:A9)'
        self.persona.save()
        wb=self.descargar()
        self.assertEqual(wb['Resumen de asistencia']['A10'].data_type,'s')
        self.assertEqual(wb['Resumen de asistencia']['B10'].data_type,'s')
        self.assertEqual(wb['Resumen de asistencia']['B10'].value,'=SUM(A1:A9)')

    def test_personal_sin_permiso_no_exporta(self):
        usuario=Usuario.objects.create_user('excel_personal',email='otro@example.invalid',dni='30303030',rol='EMPLEADO')
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse('exportar_asistencia'),self.query).status_code,403)

    def test_fecha_invertida_rechazada(self):
        self.assertEqual(self.client.get(reverse('exportar_asistencia'),{'desde':'2026-11-30','hasta':'2026-11-01'}).status_code,400)
