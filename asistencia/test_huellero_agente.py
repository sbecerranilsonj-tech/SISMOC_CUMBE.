import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from asistencia.models import MarcacionBiometrica
from asistencia.services.zkteco_live import (
    configuracion_agente, obtener_estado_agente, ordenar_prueba_conexion,
)
from core.models import Usuario

PERU = ZoneInfo("America/Lima")
TOKEN = "token-prueba-agente"
AGENTES = {
    "CHICLAYO": {"sede": "Chiclayo", "ip": "192.168.10.202", "puerto": 4370,
                 "serie": "AEWD195060148"},
    "JAEN": {"sede": "Jaén", "ip": "192.168.10.203", "puerto": 4370,
             "serie": "OTRA-SERIE"},
}


@override_settings(HUELLERO_AGENT_TOKEN=TOKEN, HUELLERO_AGENTES=AGENTES)
class AgenteHuelleroTests(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = Usuario.objects.create_user(
            "contadora-agente", email="agente@example.invalid",
            dni="44556677", rol="CONTADORA", first_name="MARIA",
            last_name="PEREZ GARCIA")
        self.client.force_login(self.usuario)

    def _agente(self, ruta, datos=None, metodo="get", agente_id="CHICLAYO"):
        cabeceras = {"HTTP_AUTHORIZATION": "Bearer " + TOKEN,
                     "HTTP_X_AGENTE_ID": agente_id}
        if metodo == "get":
            return self.client.get(reverse(ruta), **cabeceras)
        return self.client.post(
            reverse(ruta), data=json.dumps(datos or {}),
            content_type="application/json", **cabeceras)

    def test_configuracion_usa_agentes_por_sede(self):
        config = configuracion_agente()
        self.assertEqual(config["agentes"][0]["ip"], "192.168.10.202")
        self.assertEqual(config["agentes"][0]["sede"], "Chiclayo")
        self.assertEqual(len(config["agentes"]), 2)
        respuesta = self.client.get(reverse("dashboard"), {"vista": "huellero"})
        self.assertContains(respuesta, "192.168.10.202")
        self.assertContains(respuesta, "SEDE / AGENTE")
        self.assertContains(respuesta, "CHICLAYO")
        self.assertContains(respuesta, "JAEN")
        self.assertContains(respuesta, "function abrirConfigHuellero")

    def test_agente_necesita_token(self):
        self.assertEqual(self.client.get(reverse("agente_comando")).status_code, 403)
        self.assertEqual(self.client.post(reverse("agente_reportar"),
                         data="{}", content_type="application/json").status_code, 403)

    def test_prueba_de_conexion_es_dirigida_a_una_sede(self):
        ordenar_prueba_conexion("CHICLAYO")
        self.assertEqual(self._agente("agente_comando").json()["comando"]["agente_id"], "CHICLAYO")
        self.assertEqual(self._agente("agente_comando").json()["comando"], {})
        self.assertEqual(self._agente("agente_comando", agente_id="JAEN").json()["comando"], {})

    def test_reporte_guarda_marcas_y_evita_duplicados(self):
        marca = {"uid": 101, "user_id": 5, "nombre": "MARIA PEREZ",
                 "fecha_hora": datetime(2026, 11, 26, 7, 30, tzinfo=PERU).isoformat(),
                 "tipo_evento": "ENTRADA"}
        estado = {"fecha": "26/11/2026 08:00:00", "conectado": True,
                  "numero_serie": "AEWD195060148", "modelo": "MB360"}
        primera = self._agente("agente_reportar",
                               {"estado": estado, "marcas": [marca]}, "post").json()
        self.assertEqual(primera["creadas"], 1)
        guardada = MarcacionBiometrica.objects.get()
        self.assertEqual(guardada.usuario, self.usuario)
        self.assertEqual(guardada.sede, "Chiclayo")
        self.assertEqual(guardada.estado_reportado, "Refrigerio manana")
        self.assertEqual(guardada.dispositivo_ip, "192.168.10.202")
        segunda = self._agente("agente_reportar",
                               {"estado": estado, "marcas": [marca]}, "post").json()
        self.assertEqual(segunda["duplicadas"], 1)
        self.assertEqual(MarcacionBiometrica.objects.count(), 1)

    def test_identificacion_por_nombre_no_por_id_repetido(self):
        otro = Usuario.objects.create_user(
            "otro-agente", email="otro@example.invalid", dni="99887766",
            rol="ADMINISTRATIVO", first_name="JUAN",
            last_name="TORRES LOPEZ", agencia_sede="Jaén")
        # El mismo user_id en otra sede: el nombre decide quién es.
        marcas = [
            {"uid": 201, "user_id": 5, "nombre": "JUAN TORRES",
             "fecha_hora": datetime(2026, 11, 26, 8, 0, tzinfo=PERU).isoformat()},
            {"uid": 202, "user_id": 5, "nombre": "PERSONA SIN FICHA",
             "fecha_hora": datetime(2026, 11, 26, 8, 5, tzinfo=PERU).isoformat()},
        ]
        self._agente("agente_reportar", {"serie": "AEWD195060148", "marcas": marcas}, "post")
        Juan = MarcacionBiometrica.objects.filter(nombre_empleado="JUAN TORRES").get()
        self.assertEqual(Juan.usuario, otro)
        sin_ficha = MarcacionBiometrica.objects.filter(nombre_empleado="PERSONA SIN FICHA").get()
        self.assertIsNone(sin_ficha.usuario)
        self.assertIn("Por identificar", sin_ficha.estado_reportado)

    def test_marca_fuera_de_ventana_es_observacion_sin_descuento(self):
        marca = {"uid": 102, "user_id": 5, "nombre": "MARIA PEREZ",
                 "fecha_hora": datetime(2026, 11, 26, 12, 0, tzinfo=PERU).isoformat()}
        self._agente("agente_reportar", {"serie": "AEWD195060148", "marcas": [marca]}, "post")
        guardada = MarcacionBiometrica.objects.get()
        self.assertEqual(guardada.estado_reportado, "Fuera de ventana de refrigerio")
        self.assertTrue(guardada.es_valida)

    def test_web_solo_para_gestores_y_estado_por_sede(self):
        respuesta = self.client.get(reverse("agente_estado_web"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("CHICLAYO", respuesta.json()["estados"])
        prueba = self.client.post(reverse("agente_prueba_web"), {"agente_id": "JAEN"})
        self.assertEqual(prueba.json()["comando"]["agente_id"], "JAEN")
        estado = self.client.get(reverse("agente_estado_web")).json()
        self.assertTrue(estado["comandos_pendientes"]["JAEN"])
        self.assertFalse(estado["comandos_pendientes"]["CHICLAYO"])
        otro = Usuario.objects.create_user("empleado-agente", email="empleado@example.invalid",
                                           dni="11223344", rol="ADMINISTRATIVO")
        self.client.force_login(otro)
        self.assertEqual(self.client.get(reverse("agente_estado_web")).status_code, 403)
        self.assertEqual(self.client.post(reverse("agente_prueba_web")).status_code, 403)

    def test_tabla_huellero_filtra_por_rango_y_muestra_sede(self):
        hoy = timezone.localdate()
        ayer = hoy - timedelta(days=1)
        marcas = [
            {"uid": 301, "user_id": 5, "nombre": "MARIA PEREZ",
             "fecha_hora": datetime(ayer.year, ayer.month, ayer.day, 8, 0, tzinfo=PERU).isoformat()},
            {"uid": 302, "user_id": 5, "nombre": "MARIA PEREZ",
             "fecha_hora": datetime(hoy.year, hoy.month, hoy.day, 8, 0, tzinfo=PERU).isoformat()},
        ]
        self._agente("agente_reportar", {"serie": "AEWD195060148", "marcas": marcas}, "post")
        otro_dia = self.client.get(reverse("registros_huellero"),
                                   {"desde": str(ayer), "hasta": str(ayer)}).json()
        self.assertEqual(otro_dia["total"], 1)
        self.assertEqual(otro_dia["registros"][0]["sede"], "Chiclayo")
        rango = self.client.get(reverse("registros_huellero"),
                                {"desde": str(ayer), "hasta": str(hoy)}).json()
        self.assertEqual(rango["total"], 2)

    def test_estado_reportado_por_el_agente_aparece_en_el_panel(self):
        estado = {"fecha": "26/11/2026 09:00:00", "conectado": True,
                  "numero_serie": "AEWD195060148", "modelo": "MB360"}
        self._agente("agente_reportar", {"estado": estado, "marcas": []}, "post")
        self.assertEqual(obtener_estado_agente()["numero_serie"], "AEWD195060148")
        respuesta = self.client.get(reverse("dashboard"), {"vista": "huellero"})
        self.assertContains(respuesta, "AEWD195060148")
