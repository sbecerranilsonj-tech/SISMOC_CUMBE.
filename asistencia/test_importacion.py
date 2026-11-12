from datetime import datetime, time
from io import BytesIO
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
import openpyxl

from core.models import Usuario
from asistencia.models import (
    IdentidadBiometrica, MarcacionBiometrica, CargaArchivoAsistencia,
    FilaImportacionBiometrica, ResumenAsistenciaDiaria, CierreAsistencia,
)
from asistencia.services.zkteco_parser import ZKTecoExcelParser


def archivo_prueba(hojas):
    # Libro mínimo de prueba en memoria; no modifica los archivos del usuario.
    libro = openpyxl.Workbook()
    libro.remove(libro.active)
    for nombre, filas in hojas.items():
        hoja = libro.create_sheet(nombre)
        for fila in filas:
            hoja.append(fila)
    memoria = BytesIO()
    libro.save(memoria)
    memoria.seek(0)
    return memoria


CABECERA = ["Departmento", "Nombre", "No.", "Fecha/Hora", "Estado", "ID Equipo", "Cód. verificacion"]
FECHA = datetime(2026, 8, 1, 3, 40, 11)


class ImportacionBiometricaTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user("teran", email="teran@example.invalid", dni="11223344", first_name="Terán", agencia_sede="Cajamarca")
        self.admin = Usuario.objects.create_user("admin", email="admin@example.invalid", dni="22334455", rol="ADMINISTRADOR")

    def importar(self, hojas):
        return ZKTecoExcelParser(archivo_prueba(hojas), "prueba.xlsx", self.admin).procesar()

    def test_codigo_corto_se_guarda_sin_dni_inventado_y_con_zona(self):
        resultado = self.importar({"CAJAMARCA ": [CABECERA, ["OUR COMPANY", "2", "2", FECHA, "M/Ent", "1", "FACE"]]})
        identidad = IdentidadBiometrica.objects.get()
        marca = MarcacionBiometrica.objects.get()
        self.assertEqual(identidad.codigo, "2")
        self.assertEqual(identidad.sede, "CAJAMARCA")
        self.assertEqual(marca.dni, "")
        self.assertEqual(marca.zkteco_user_id, 2)
        self.assertEqual(marca.tipo_evento, "SIN_CLASIFICAR")
        self.assertEqual(marca.estado_reportado, "M/Ent")
        self.assertEqual(marca.departamento_reportado, "OUR COMPANY")
        self.assertEqual(timezone.localtime(marca.fecha_hora).hour, 3)
        self.assertEqual(resultado["marcaciones_nuevas"], 1)
        self.assertEqual(Usuario.objects.count(), 2)

    def test_compania_original_visible_en_marcaciones_ya_importadas(self):
        self.importar({"CAJAMARCA": [CABECERA, ["OUR COMPANY", "Pasapera", "13", FECHA, "M/Ent", "1", "FACE"]]})
        self.client.force_login(self.admin)
        res = self.client.get(reverse("dashboard"), {"vista": "excel-zk", "codigo_biometrico": IdentidadBiometrica.objects.get().pk})
        self.assertContains(res, "Departamento / compañía")
        self.assertContains(res, "OUR COMPANY")
        self.assertEqual(MarcacionBiometrica.objects.count(), 1)

    def test_asociacion_previa_reconoce_codigo_y_reimportacion_no_duplica(self):
        IdentidadBiometrica.objects.create(sede="CAJAMARCA", equipo="1", codigo="2", nombre="Terán", usuario=self.usuario)
        hojas = {"CAJAMARCA": [CABECERA, ["", "2", "2", FECHA, "", "1", "FACE"]]}
        self.importar(hojas)
        segunda = self.importar(hojas)
        marca = MarcacionBiometrica.objects.get()
        self.assertEqual(marca.usuario, self.usuario)
        self.assertEqual(marca.dni, self.usuario.dni)
        self.assertEqual(segunda["marcaciones_nuevas"], 0)
        self.assertEqual(segunda["marcaciones_repetidas"], 1)
        self.assertEqual(FilaImportacionBiometrica.objects.count(), 2)
        self.assertEqual(ResumenAsistenciaDiaria.objects.get().horas_trabajadas, 0)

    def test_mismo_codigo_corto_en_dos_sedes_son_identidades_distintas(self):
        fila = ["", "2", "2", FECHA, "", "1", "FACE"]
        self.importar({"CAJAMARCA": [CABECERA, fila], "JAEN": [CABECERA, fila]})
        self.assertEqual(IdentidadBiometrica.objects.count(), 2)
        self.assertEqual(MarcacionBiometrica.objects.count(), 2)

    def test_marca_copiada_entre_hojas_conserva_ambas_procedencias(self):
        fila = ["", "Terán", self.usuario.dni, FECHA, "", "1", "FP"]
        resultado = self.importar({"CHICLAYO": [CABECERA, fila], "PAUL HARRIS": [CABECERA, fila]})
        self.assertEqual(resultado["filas_procesadas"], 2)
        self.assertEqual(resultado["marcaciones_nuevas"], 1)
        self.assertEqual(resultado["marcaciones_repetidas"], 1)
        self.assertEqual(FilaImportacionBiometrica.objects.count(), 2)

    def test_error_de_fecha_no_guarda_importacion_parcial(self):
        with self.assertRaises(ValidationError):
            self.importar({"CAJAMARCA": [CABECERA, ["", "2", "2", FECHA, "", "1", "FACE"], ["", "2", "2", "7546-10-10", "", "1", "FACE"]]})
        self.assertFalse(MarcacionBiometrica.objects.exists())
        self.assertFalse(CargaArchivoAsistencia.objects.exists())

    def test_no_interpreta_hoja_individual_como_exportacion(self):
        with self.assertRaises(ValidationError):
            self.importar({"TERAN": [["MARTES DESCANSA"], [None, None, "2", FECHA]]})
        self.assertFalse(IdentidadBiometrica.objects.exists())

    def test_exportacion_generica_cix_reutiliza_sede_e_identidad(self):
        identidad=IdentidadBiometrica.objects.create(sede='CHICLAYO',equipo='104',codigo='12345678',nombre='Persona conocida',usuario=self.usuario)
        fila=['Esta Compañia','Persona exportada','12345678',FECHA,'','104','FP']
        for nombre in ['asistencia octubre cix.xls','asistencia_octubre_CIX.xls']:
            resultado=ZKTecoExcelParser(archivo_prueba({'Sheet 1':[CABECERA,fila]}),nombre,self.admin).procesar()
        marca=MarcacionBiometrica.objects.get()
        self.assertEqual(marca.identidad_biometrica_id,identidad.pk)
        self.assertEqual(resultado['marcaciones_nuevas'],0)
        self.assertEqual(IdentidadBiometrica.objects.count(),1)
        self.assertEqual(set(FilaImportacionBiometrica.objects.values_list('hoja',flat=True)),{'Sheet 1'})

    def test_hoja_generica_sin_sede_o_ambigua_no_crea_asociaciones(self):
        fila=['','Persona','12',FECHA,'','104','FP']
        for nombre in ['exportacion.xls','asistencia cix cajamarca.xls']:
            with self.assertRaises(ValidationError):
                ZKTecoExcelParser(archivo_prueba({'Sheet 1':[CABECERA,fila]}),nombre,self.admin).procesar()
        self.assertFalse(CargaArchivoAsistencia.objects.exists())

    def test_sede_explicita_solo_resuelve_hojas_genericas(self):
        fila=['','Persona','12',FECHA,'','104','FP']
        r,_,_=ZKTecoExcelParser(archivo_prueba({'Sheet 1':[CABECERA,fila],'CAJAMARCA':[CABECERA,fila]}),'exportacion.xlsx',sede='CHICLAYO').leer()
        self.assertEqual([m['sede'] for m in r],['CHICLAYO','CAJAMARCA'])

    def test_asociacion_desde_pantalla_persiste_para_proximas_cargas(self):
        self.importar({"CAJAMARCA": [CABECERA, ["", "2", "2", FECHA, "", "1", "FACE"]]})
        identidad = IdentidadBiometrica.objects.get()
        self.client.force_login(self.admin)
        res = self.client.post(reverse("vincular_identidad", args=[identidad.pk]), {"usuario": self.usuario.pk, "nombre": "Terán", "motivo": "Ficha confirmada"})
        self.assertEqual(res.status_code, 302)
        identidad.refresh_from_db()
        self.assertEqual(identidad.usuario, self.usuario)
        self.assertEqual(MarcacionBiometrica.objects.get().usuario, self.usuario)
        self.assertTrue(ResumenAsistenciaDiaria.objects.filter(usuario=self.usuario).exists())

    def test_periodo_cerrado_cancela_toda_la_carga(self):
        CierreAsistencia.objects.create(fecha_inicio=FECHA.date(), fecha_fin=FECHA.date(), total_jornadas=0)
        with self.assertRaises(ValidationError):
            self.importar({"CAJAMARCA": [CABECERA, ["", "2", "2", FECHA, "", "1", "FACE"]]})
        self.assertFalse(IdentidadBiometrica.objects.exists())
        self.assertFalse(CargaArchivoAsistencia.objects.exists())

    def test_carga_web_devuelve_conteos_y_no_crea_cuentas(self):
        self.client.force_login(self.admin)
        memoria = archivo_prueba({"CAJAMARCA": [CABECERA, ["", "2", "2", FECHA, "", "1", "FACE"]]})
        archivo = SimpleUploadedFile("prueba.xlsx", memoria.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        res = self.client.post(reverse("importar_excel_web"), {"file": archivo})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["codigos_biometricos"], 1)
        self.assertEqual(Usuario.objects.count(), 2)

    def test_signal_acepta_fecha_sin_zona_horaria(self):
        marca = MarcacionBiometrica.objects.create(usuario=self.usuario, dni=self.usuario.dni, fecha_hora=FECHA)
        self.assertTrue(timezone.is_aware(marca.fecha_hora))

    def test_consulta_por_codigo_no_exige_crear_cuenta_del_trabajador(self):
        self.importar({"CAJAMARCA": [CABECERA, ["", "Terán", "2", FECHA, "", "1", "FACE"]]})
        identidad = IdentidadBiometrica.objects.get()
        self.client.force_login(self.admin)
        res = self.client.get(reverse("dashboard"), {"vista": "excel-zk", "codigo_biometrico": identidad.pk})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["identidad_consultada"], identidad)
        self.assertEqual(len(res.context["marcas_codigo"]), 1)
        self.assertContains(res, "Terán")
        self.assertContains(res, "FACE")
        self.assertIsNone(identidad.usuario_id)
