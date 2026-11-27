"""Los errores de API no exponen datos personales ni detalle interno."""
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from ninja.errors import HttpError

from asistencia.api import subir_excel_zkteco
from core.api import crear_usuario
from core.models import Usuario
from core.schemas import UsuarioCreateSchema


class ErroresSinPiiTests(TestCase):
    def test_dni_no_aparece_en_error_de_creacion(self):
        Usuario.objects.create_user(
            'duplicado-dni', dni='12345678', rol='CONTADORA')
        datos = UsuarioCreateSchema(
            dni='12345678', username='nuevo-usuario',
            password='ClaveSegura2026!', first_name='Nuevo',
            last_name='Usuario', rol='CONTADORA')
        with self.assertRaises(HttpError) as error:
            crear_usuario(None, datos)
        self.assertNotIn('12345678', error.exception.message)

    @patch('asistencia.api.ZKTecoExcelParser')
    def test_error_de_excel_no_devuelve_detalle_interno(self, parser):
        parser.return_value.procesar.side_effect = RuntimeError('ruta/secreta/interna')
        archivo = SimpleUploadedFile('reporte.xlsx', b'PK\x03\x04')
        with self.assertRaises(HttpError) as error:
            subir_excel_zkteco(SimpleNamespace(auth=None), archivo)
        self.assertNotIn('secreta', error.exception.message)
