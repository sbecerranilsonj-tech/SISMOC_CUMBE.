from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from core.models import Usuario
from .models import EstadoCuenta, Movimiento
from .forms import MovimientoForm, ImportarForm


class FlujoBancarioTests(TestCase):
    def test_importador_y_revision_comparten_pantalla_y_menu(self):
        response=self.client.get(reverse('bancos_importar'))
        self.assertContains(response,'Estados de cuenta por mes')
        self.assertContains(response,'Yape prueba')
        self.assertContains(response,'Validar y pasar a control bancario')
        self.assertContains(response,'id="banco-upload-directo"')
        self.assertContains(response,'data-banco-upload')
        self.assertNotContains(response,'<span>Validar movimientos bancarios</span>')
        self.assertContains(response,f'action="{reverse("bancos_detalle",args=[self.estado.pk])}"')
        self.assertRedirects(self.client.get(reverse('bancos_validacion')),reverse('bancos_importar')+'?situacion=PENDIENTE')

    def test_ficha_al_inicio_se_actualiza_con_el_mes(self):
        agosto = EstadoCuenta.objects.create(cuenta='999-AGOSTO', inicio=date(2026,8,1), fin=date(2026,8,31), saldo_inicial=0, saldo_final=0, huella='d'*64, creado_por=self.contadora)
        for mes, estado in [('2026-07', self.estado), ('2026-08', agosto)]:
            response = self.client.get(reverse('bancos_importar'), {'mes':mes, 'archivo':self.estado.pk})
            self.assertEqual(response.context['estado'].pk, estado.pk)
            html = response.content.decode()
            self.assertLess(html.index('class="banco-ficha"'), html.index('class="banco-import-list"'))
            self.assertContains(response, estado.cuenta)
            self.assertEqual(html.count('class="banco-ficha"'), 1)

    def test_meses_cuentan_movimientos_sin_duplicar_archivos(self):
        Movimiento.objects.create(estado_cuenta=self.estado,orden=2,pagina=1,fecha=date(2026,7,2),fecha_valor=date(2026,7,2),descripcion='Otro abono',abono=5)
        self.estado.saldo_final=150;self.estado.save()
        response=self.client.get(reverse('bancos_importar'),{'mes':'2026-07'})
        self.assertEqual(response.context['meses'][0]['archivos'],1)
        self.assertEqual(response.context['meses'][0]['total'],2)
        self.assertEqual(response.context['pagina'].paginator.count,2)
        self.assertEqual(response.context['pagina'][1].saldo,150)

    def test_busqueda_conserva_saldo_y_cuenta_seleccionada(self):
        Movimiento.objects.create(estado_cuenta=self.estado,orden=2,pagina=1,fecha=date(2026,7,2),fecha_valor=date(2026,7,2),descripcion='Segundo movimiento',abono=5)
        response=self.client.get(reverse('bancos_importar'),{'archivo':self.estado.pk,'q':'Segundo'})
        self.assertEqual(response.context['pagina'].paginator.count,1)
        self.assertEqual(response.context['pagina'][0].saldo,150)
        self.assertIn(f'archivo={self.estado.pk}',response.context['consulta'])

    def test_pdf_invalido_muestra_error_junto_al_archivo_existente(self):
        response=self.client.post(reverse('bancos_importar'),{'pdf':SimpleUploadedFile('estado.pdf',b'no es pdf')})
        self.assertContains(response,'cabecera PDF')
        self.assertContains(response,'Yape prueba')
        self.assertEqual(EstadoCuenta.objects.count(),1)
    def test_pdf_con_preambulo_y_archivo_previamente_leido(self):
        archivo = SimpleUploadedFile('estado.pdf', b'\xef\xbb\xbf\r\n%PDF-1.7\ncontenido')
        archivo.read()
        form = ImportarForm(files={'pdf': archivo})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['pdf'].tell(), 0)

    def test_archivo_renombrado_no_es_pdf(self):
        form = ImportarForm(files={'pdf': SimpleUploadedFile('estado.pdf', b'<html>No es PDF</html>')})
        self.assertFalse(form.is_valid())
        self.assertIn('cabecera PDF', str(form.errors))

    def test_dependencia_ausente_informa_causa_sin_guardar(self):
        with patch('bancos.views.extraer', side_effect=ModuleNotFoundError("No module named 'pdfplumber'", name='pdfplumber')):
            response = self.client.post(reverse('bancos_importar'), {'pdf': SimpleUploadedFile('nuevo.pdf', b'%PDF-1.7\nnuevo')})
        self.assertContains(response, 'El lector PDF no está instalado en el servidor')
        self.assertEqual(EstadoCuenta.objects.count(), 1)

    def setUp(self):
        self.contadora = Usuario.objects.create_user(username='contadora_bancos', email='contadora@example.test', dni='93000001', password='prueba', rol='CONTADORA')
        self.client.force_login(self.contadora)
        self.estado = EstadoCuenta.objects.create(cuenta='305-00459702-0-32', inicio=date(2026, 7, 1), fin=date(2026, 7, 31), saldo_inicial=100, saldo_final=145, huella='a' * 64, creado_por=self.contadora)
        self.movimiento = Movimiento.objects.create(estado_cuenta=self.estado, orden=1, pagina=1, fecha=date(2026, 7, 1), fecha_valor=date(2026, 7, 1), descripcion='Yape prueba', abono=45, cargo=0)

    def test_pendientes_no_aparecen_hasta_validar_y_no_se_duplican(self):
        self.assertEqual(self.client.get(reverse('bancos_control')).context['pagina'].paginator.count, 0)
        url = reverse('bancos_detalle', args=[self.estado.pk])
        self.assertRedirects(self.client.post(url, {'accion': 'validar'}), reverse('bancos_control'))
        self.assertEqual(self.client.get(reverse('bancos_control')).context['pagina'].paginator.count, 1)
        self.client.post(url, {'accion': 'validar'})
        self.assertEqual(Movimiento.objects.count(), 1)
        self.assertEqual(self.estado.revisiones.count(), 1)

    def test_diferencias_e_incidencias_bloquean_validacion(self):
        self.estado.saldo_final = 150
        self.estado.save()
        url = reverse('bancos_detalle', args=[self.estado.pk])
        self.client.post(url, {'accion': 'validar'})
        self.estado.refresh_from_db()
        self.assertEqual(self.estado.estado, 'PENDIENTE')
        self.estado.saldo_final = 145
        self.estado.incidencias = ['línea incompleta']
        self.estado.save()
        self.client.post(url, {'accion': 'validar'})
        self.estado.refresh_from_db()
        self.assertEqual(self.estado.estado, 'PENDIENTE')

    def test_personal_sin_permiso_no_ve_pdf_ni_bancos(self):
        usuario = Usuario.objects.create_user(username='sin_permiso', email='conductor@example.test', dni='93000002', rol='CONDUCTOR')
        self.client.force_login(usuario)
        for nombre, args in [('bancos_importar', []), ('bancos_validacion', []), ('bancos_control', []), ('bancos_detalle', [self.estado.pk]), ('bancos_pdf', [self.estado.pk])]:
            self.assertEqual(self.client.get(reverse(nombre, args=args)).status_code, 403)

    def test_importacion_repetida_abre_existente(self):
        import hashlib
        contenido = b'%PDF-prueba'
        self.estado.huella = hashlib.sha256(contenido).hexdigest()
        self.estado.save()
        with patch('bancos.views.extraer') as parser:
            response = self.client.post(reverse('bancos_importar'), {'pdf': SimpleUploadedFile('estado.pdf', contenido)})
            self.assertRedirects(response, reverse('bancos_detalle', args=[self.estado.pk]))
            parser.assert_not_called()

    def test_correccion_auditada_y_bloqueada_despues_de_validar(self):
        datos = {'accion': 'editar', 'movimiento': self.movimiento.pk, 'fecha': '2026-07-01', 'fecha_valor': '2026-07-01', 'descripcion': 'Corregida', 'cargo': '0', 'abono': '45', 'observacion': 'Verificado contra PDF'}
        url = reverse('bancos_detalle', args=[self.estado.pk])
        self.client.post(url, datos)
        self.movimiento.refresh_from_db()
        self.assertEqual(self.movimiento.descripcion, 'Corregida')
        self.assertEqual(self.estado.revisiones.get().detalle['antes']['descripcion'], 'Yape prueba')
        self.client.post(url, {'accion': 'validar'})
        datos['descripcion'] = 'No permitido'
        self.client.post(url, datos)
        self.movimiento.refresh_from_db()
        self.assertEqual(self.movimiento.descripcion, 'Corregida')

    def test_formulario_rechaza_importes_ambiguos(self):
        form = MovimientoForm({'fecha': '2026-07-01', 'fecha_valor': '2026-07-01', 'descripcion': 'Prueba', 'cargo': '45', 'abono': '45'}, instance=self.movimiento)
        self.assertFalse(form.is_valid())

    def test_descargar_diagnostico_no_expone_movimientos_ni_cuenta_completa(self):
        with patch('bancos.views.extraer') as extraer_pdf, patch('django.db.models.fields.files.FieldFile.open') as abrir_archivo:
            response = self.client.get(reverse('bancos_diagnostico', args=[self.estado.pk]))
            extraer_pdf.assert_not_called()
            abrir_archivo.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertContains(response, 'MOTIVOS DEL BLOQUEO')
        self.assertNotContains(response, self.estado.cuenta)
        self.assertNotContains(response, self.movimiento.descripcion)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('bancos_diagnostico', args=[self.estado.pk])).status_code, 302)

    def test_bloqueo_explicito_e_historial_legible(self):
        from .models import Revision
        self.estado.incidencias = ['No se pudieron verificar los totales del documento.']
        self.estado.save()
        Revision.objects.create(estado_cuenta=self.estado, responsable=self.contadora, detalle={'accion': 'Importación', 'movimientos': 1})
        response = self.client.get(reverse('bancos_detalle', args=[self.estado.pk]))
        self.assertContains(response, 'La validación está bloqueada por estos motivos')
        self.assertContains(response, 'No se pudieron verificar los totales del documento.')
        self.assertContains(response, 'Se importaron')
        self.assertNotContains(response, '&#x27;accion&#x27;')

    def test_recomprobar_actualiza_incidencias_sin_duplicar(self):
        from io import BytesIO
        self.estado.incidencias = ['Totales no reconocidos por el lector anterior']
        self.estado.save()
        datos = {k: getattr(self.estado, k) for k in ('cuenta', 'inicio', 'fin', 'saldo_inicial', 'saldo_final')}
        datos['incidencias'] = []
        url = reverse('bancos_detalle', args=[self.estado.pk])
        with patch('django.db.models.fields.files.FieldFile.open', return_value=BytesIO(b'%PDF-prueba')), patch('bancos.views.extraer', return_value=(datos, [{'cargo': 0, 'abono': 45}])):
            self.client.post(url, {'accion': 'recomprobar'})
        self.estado.refresh_from_db()
        self.assertEqual(self.estado.incidencias, [])
        self.assertEqual(self.estado.movimientos.count(), 1)
        self.assertEqual(self.estado.estado, 'PENDIENTE')
        self.client.post(url, {'accion': 'validar'})
        self.estado.refresh_from_db()
        self.assertEqual(self.estado.estado, 'VALIDADO')

    def test_paginas_renderizan(self):
        for nombre in ['bancos_importar', 'bancos_validacion', 'bancos_control']:
            response = self.client.get(reverse(nombre), follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'index.html')
            self.assertContains(response, 'id="navegacion-principal"')
            self.assertContains(response, 'id="bancos-workspace"')
        self.assertContains(self.client.get(reverse('bancos_detalle', args=[self.estado.pk])), 'Yape prueba')
