import json
from datetime import datetime, timedelta
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase
from django.urls import reverse
from core.models import Usuario
from asistencia.models import CargaArchivoAsistencia, MarcacionBiometrica, FilaImportacionBiometrica
from asistencia.test_importacion import archivo_prueba, CABECERA


class ProgresoImportacionTests(TransactionTestCase):
    def setUp(self):
        self.actor=Usuario.objects.create_user('progreso_prueba',email='progreso@example.invalid',dni='12345678',rol='CONTADORA')
        self.client.force_login(self.actor)
        self.url=reverse('importar_excel_web')

    def archivo(self, cantidad=25):
        filas=[CABECERA]+[['','Persona prueba','20',datetime(2026,8,3,8)+timedelta(minutes=i),'','104','FP'] for i in range(cantidad)]
        return SimpleUploadedFile('asistencia CHICLAYO.xlsx',archivo_prueba({'CHICLAYO':filas}).getvalue())

    def eventos(self, archivo):
        res=self.client.post(self.url,{'file':archivo,'progreso':'si'})
        self.assertTrue(res.streaming)
        self.assertEqual(res['X-Accel-Buffering'],'no')
        return [json.loads(chunk) for chunk in res.streaming_content]

    def test_avance_monotono_y_cien_solo_despues_de_guardar(self):
        eventos=self.eventos(self.archivo())
        progreso=[e for e in eventos if e['tipo']=='progreso']
        self.assertTrue(all(e['porcentaje']<100 for e in progreso))
        porcentajes=[e['porcentaje'] for e in progreso]
        self.assertEqual(porcentajes,sorted(porcentajes))
        self.assertTrue(any(e['etapa']=='registrando' and 0<e['actual']<e['total'] for e in progreso))
        self.assertEqual(eventos[-1]['tipo'],'completado')
        self.assertEqual(eventos[-1]['porcentaje'],100)
        self.assertEqual(eventos[-1]['resultado']['filas_procesadas'],25)
        self.assertEqual(MarcacionBiometrica.objects.count(),25)
        self.assertEqual(CargaArchivoAsistencia.objects.get().estado,'COMPLETADO')

    def test_error_intermedio_revierte_todo_y_no_emite_completado(self):
        crear=FilaImportacionBiometrica.objects.create
        contador=0
        def fallar(**kwargs):
            nonlocal contador
            contador+=1
            if contador==2:raise ValidationError('Error de prueba al registrar la fila.')
            return crear(**kwargs)
        with patch('asistencia.services.zkteco_parser.FilaImportacionBiometrica.objects.create',side_effect=fallar):
            eventos=self.eventos(self.archivo(3))
        self.assertEqual(eventos[-1]['tipo'],'error')
        self.assertNotIn('completado',[e['tipo'] for e in eventos])
        self.assertFalse(MarcacionBiometrica.objects.exists())
        self.assertFalse(CargaArchivoAsistencia.objects.exists())

    def test_formato_invalido_y_permisos_se_validan_antes_del_stream(self):
        self.assertEqual(self.client.post(self.url,{'file':SimpleUploadedFile('texto.txt',b'test'),'progreso':'si'}).status_code,400)
        self.actor.rol='BOLETERIA';self.actor.save()
        self.assertEqual(self.client.post(self.url,{'file':self.archivo(),'progreso':'si'}).status_code,403)
