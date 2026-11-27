"""Las subidas se validan antes de parsearlas."""
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.archivos import validar_archivo_subido


class ArchivoFalso:
    def __init__(self, nombre, tamano, inicio=b'PK\x03\x04'):
        self.name = nombre
        self.size = tamano
        self.inicio = inicio

    def read(self, cantidad=-1):
        return self.inicio

    def seek(self, posicion):
        return posicion


class SubidasSegurasTests(TestCase):
    def test_rechaza_tamano_excesivo(self):
        with self.assertRaises(ValidationError):
            validar_archivo_subido(
                ArchivoFalso('grande.xlsx', 10 * 1024 * 1024 + 1), ('.xlsx',))

    def test_rechaza_extension_no_permitida(self):
        with self.assertRaises(ValidationError):
            validar_archivo_subido(ArchivoFalso('archivo.exe', 10), ('.xlsx',))

    def test_rechaza_xlsx_que_no_es_zip(self):
        with self.assertRaises(ValidationError):
            validar_archivo_subido(
                ArchivoFalso('falso.xlsx', 10, b'NOZIP'), ('.xlsx',), verificar_zip=True)

    def test_rechaza_xls_y_xlsm_con_extension_falsa(self):
        for nombre in ('falso.xls', 'falso.xlsm'):
            with self.subTest(nombre=nombre), self.assertRaises(ValidationError):
                validar_archivo_subido(ArchivoFalso(nombre, 10, b'NOZIP'),
                                       ('.xls', '.xlsm'))
