from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from core.models import Usuario
from asistencia.models import (
    TurnoHorario, ResumenAsistenciaDiaria, MarcacionBiometrica,
    AjusteAsistencia, IncidenciaAsistencia, CorreccionEvento, CierreAsistencia,
)
from asistencia.services.revision import detalle_jornada, revisar, valores_ajustados
from asistencia.services.zkteco_live import ZKTecoLiveClient


class RevisionAsistenciaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dia = timezone.localdate() - timedelta(days=10)
        cls.turno = TurnoHorario.objects.create(nombre="Turno mañana", hora_entrada=time(8), hora_salida=time(17), hora_inicio_refrigerio=time(12), hora_fin_refrigerio=time(12, 45))
        cls.admin = Usuario.objects.create_user("admin_prueba", email="admin@example.invalid", dni="10000001", rol="ADMINISTRADOR")
        cls.contadora = Usuario.objects.create_user("contadora_prueba", email="contadora@example.invalid", dni="10000002", rol="CONTADORA")
        cls.empleado = Usuario.objects.create_user("empleado_prueba", email="empleado@example.invalid", first_name="Trabajador de prueba", dni="10000003", rol="BOLETERIA", turno=cls.turno, agencia_sede="Chiclayo")
        cls.otro = Usuario.objects.create_user("otro_prueba", email="otro@example.invalid", first_name="Persona reservada", dni="10000004", rol="ADMINISTRATIVO", turno=cls.turno, agencia_sede="Jaén")
        cls.resumen = ResumenAsistenciaDiaria.objects.create(usuario=cls.empleado, fecha=cls.dia, primera_entrada=time(8), ultima_salida=time(17), horas_trabajadas=Decimal("8.25"), turno_aplicado=cls.turno)
        for hora, tipo in [(time(8), "ENTRADA"), (time(12), "SALIDA_REFRIGERIO"), (time(12, 45), "RETORNO_REFRIGERIO"), (time(17), "SALIDA")]:
            MarcacionBiometrica.objects.create(usuario=cls.empleado, dni=cls.empleado.dni, fecha_hora=timezone.make_aware(datetime.combine(cls.dia, hora)), tipo_evento=tipo)
        cls.resumen_otro = ResumenAsistenciaDiaria.objects.create(usuario=cls.otro, fecha=cls.dia, primera_entrada=time(8), ultima_salida=time(17), horas_trabajadas=8)

    def setUp(self):
        self.filtros = {"vista": "asistencia", "desde": self.dia.isoformat(), "hasta": self.dia.isoformat()}

    def post_jornada(self, **data):
        return self.client.post(reverse("accion_jornada", args=[self.resumen.pk]), {**self.filtros, **data})

    def test_reconstruye_refrigerio_real_y_tramos(self):
        d = detalle_jornada(self.resumen)
        self.assertTrue(d["completa"])
        self.assertEqual(d["refrigerio"], "00:45:00")
        self.assertEqual(d["trabajo_reconstruido"], "08:15:00")
        self.assertEqual(d["deficit_minutos"], 0)
        self.assertEqual(d["bloqueos"], [])

    def test_cruce_de_medianoche(self):
        turno = TurnoHorario.objects.create(nombre="Noche", hora_entrada=time(20), hora_salida=time(4))
        dia = self.dia - timedelta(days=2)
        r = ResumenAsistenciaDiaria.objects.create(usuario=self.empleado, fecha=dia, primera_entrada=time(20), ultima_salida=time(4), horas_trabajadas=8, turno_aplicado=turno)
        for fecha, hora, tipo in [(dia, time(20), "ENTRADA"), (dia + timedelta(days=1), time(4), "SALIDA")]:
            MarcacionBiometrica.objects.create(usuario=self.empleado, dni=self.empleado.dni, fecha_hora=timezone.make_aware(datetime.combine(fecha, hora)), tipo_evento=tipo)
        d = detalle_jornada(r)
        self.assertTrue(d["completa"])
        self.assertEqual(d["trabajo_reconstruido"], "08:00:00")

    def test_filtros_y_plantillas_detalle(self):
        self.client.force_login(self.contadora)
        res = self.client.get(reverse("dashboard"), {**self.filtros, "detalle": self.resumen.pk, "sede": "Chiclayo"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "08:15:00")
        self.assertContains(res, "00:45:00")
        self.assertContains(res, "Aprobar jornada")
        self.assertContains(res, "Cuadro de control diario · Formato del Excel")
        self.assertContains(res, "Feriado y/o descanso")
        self.assertEqual(res.context["total_jornadas"], 1)
        self.assertEqual([r.usuario_id for r in res.context["pagina_asistencia"]], [self.empleado.pk])

    def test_cuadro_excel_reproduce_horas_de_carlos(self):
        self.turno.hora_fin_refrigerio = time(13)
        self.turno.save()
        self.resumen.primera_entrada = time(3, 40, 11)
        self.resumen.ultima_salida = time(15, 10, 9)
        self.resumen.save()
        MarcacionBiometrica.objects.filter(usuario=self.empleado).delete()
        for hora, tipo in [(time(3, 40, 11), "ENTRADA"), (time(12, 23, 19), "SALIDA_REFRIGERIO"), (time(12, 53, 39), "RETORNO_REFRIGERIO"), (time(15, 10, 9), "SALIDA")]:
            MarcacionBiometrica.objects.create(usuario=self.empleado, dni=self.empleado.dni, fecha_hora=timezone.make_aware(datetime.combine(self.dia, hora)), tipo_evento=tipo)
        cuadro = detalle_jornada(self.resumen)["cuadro_excel"]
        self.assertEqual(cuadro["refrigerio"], "00:30:20")
        for campo, esperado in {"trabajo": "10:59:38", "base": "08:00:00", "saldo": "02:59:38", "he25": "02:00:00", "he35": "00:59:38", "nocturnas": "02:19:49"}.items():
            self.assertEqual(cuadro["totales"][campo], esperado, campo)
        self.assertTrue(cuadro["filas"][2]["es_refrigerio"])

    def test_cuadro_excel_incompleto_no_inventa_totales(self):
        cuadro = detalle_jornada(self.resumen_otro)["cuadro_excel"]
        for campo in ["trabajo", "saldo", "he25", "he35", "nocturnas"]:
            self.assertEqual(cuadro["totales"][campo], "Por revisar")
        self.assertEqual(cuadro["descuento"], "Sin registro")

    def test_cuadro_excel_deficit_no_genera_extras_negativas(self):
        MarcacionBiometrica.objects.filter(usuario=self.empleado, tipo_evento="SALIDA").update(fecha_hora=timezone.make_aware(datetime.combine(self.dia, time(15, 45))))
        cuadro = detalle_jornada(self.resumen)["cuadro_excel"]
        self.assertEqual(cuadro["totales"]["saldo"], "−01:00:00")
        self.assertEqual(cuadro["totales"]["he25"], "00:00:00")
        self.assertEqual(cuadro["totales"]["he35"], "00:00:00")
        self.assertEqual(cuadro["descuento"], "Sin registro")

    def test_jornada_base_ocho_horas_aunque_horario_abarque_nueve(self):
        self.turno.hora_inicio_refrigerio = None
        self.turno.hora_fin_refrigerio = None
        self.turno.save()
        cuadro = detalle_jornada(self.resumen)["cuadro_excel"]
        self.assertEqual(cuadro["totales"]["base"], "08:00:00")
        self.assertEqual(cuadro["totales"]["trabajo"], "08:15:00")
        self.assertEqual(cuadro["totales"]["he25"], "00:15:00")
        self.assertEqual(cuadro["totales"]["he35"], "00:00:00")

    def test_fecha_invalida_muestra_error(self):
        self.client.force_login(self.contadora)
        res = self.client.get(reverse("dashboard"), {"desde": "incorrecto"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context["filtros"]["error"])

    def test_empleado_solo_consulta_sus_jornadas(self):
        self.client.force_login(self.empleado)
        res = self.client.get(reverse("dashboard"), self.filtros)
        self.assertEqual(res.context["total_jornadas"], 1)
        self.assertNotContains(res, "Persona reservada")
        res = self.client.get(reverse("dashboard"), {**self.filtros, "detalle": self.resumen_otro.pk})
        self.assertEqual(res.status_code, 404)
        self.assertEqual(self.post_jornada(accion="APROBADO").status_code, 403)
        self.assertEqual(self.client.get(reverse("exportar_asistencia"), self.filtros).status_code, 403)

    def test_admin_puede_observar_pero_no_aprobar(self):
        self.client.force_login(self.admin)
        self.post_jornada(accion="OBSERVADO", motivo="Revisar evidencia")
        self.resumen.refresh_from_db()
        self.assertEqual(self.resumen.estado_revision, "OBSERVADO")
        self.post_jornada(accion="APROBADO")
        self.resumen.refresh_from_db()
        self.assertFalse(self.resumen.verificado_contabilidad)

    def test_aprobacion_con_historial(self):
        self.client.force_login(self.contadora)
        self.post_jornada(accion="APROBADO", motivo="Revisado por tramos")
        self.resumen.refresh_from_db()
        self.assertTrue(self.resumen.verificado_contabilidad)
        self.assertEqual(self.resumen.revisado_por, self.contadora)
        self.assertTrue(self.resumen.historial_revision.filter(accion="Jornada aprobada").exists())

    def test_no_aprobar_con_salida_faltante(self):
        MarcacionBiometrica.objects.filter(usuario=self.empleado, tipo_evento="SALIDA").update(tipo_evento="ENTRADA")
        with self.assertRaises(ValidationError):
            revisar(self.resumen, self.contadora, "APROBADO")

    def test_ajustes_no_afectan_totales_hasta_aprobar(self):
        self.client.force_login(self.admin)
        self.post_jornada(accion="ajuste", concepto="horas_extras_25", minutos="15", motivo="Tiempo validado")
        ajuste = AjusteAsistencia.objects.get(resumen=self.resumen)
        self.assertEqual(valores_ajustados(self.resumen)["horas_extras_25"], 0)
        self.client.force_login(self.contadora)
        self.post_jornada(accion="aprobar_ajuste", registro_id=ajuste.pk)
        self.assertEqual(valores_ajustados(self.resumen)["horas_extras_25"], Decimal("0.25"))
        self.resumen.refresh_from_db()
        self.assertFalse(self.resumen.verificado_contabilidad)

    def test_incidencia_aprobada_cambia_estado_sin_inventar_marcas(self):
        r = self.resumen_otro
        r.horas_trabajadas = 0
        r.save(update_fields=["horas_trabajadas"])
        self.client.force_login(self.contadora)
        url = reverse("accion_jornada", args=[r.pk])
        self.client.post(url, {"accion": "incidencia", "tipo": "VACACIONES", "motivo": "Vacaciones autorizadas"})
        i = IncidenciaAsistencia.objects.get(resumen=r)
        self.client.post(url, {"accion": "aprobar_incidencia", "registro_id": i.pk})
        r.refresh_from_db()
        self.assertEqual(r.estado, "VACACIONES")
        self.assertEqual(MarcacionBiometrica.objects.filter(usuario=self.otro).count(), 0)

    def test_correccion_preserva_evento_original(self):
        marca = MarcacionBiometrica.objects.get(usuario=self.empleado, tipo_evento="SALIDA")
        self.client.force_login(self.admin)
        self.post_jornada(accion="corregir_evento", marcacion_id=marca.pk, tipo_evento="SALIDA_REFRIGERIO", motivo="Error del equipo")
        marca.refresh_from_db()
        self.assertEqual(marca.tipo_evento, "SALIDA")
        self.assertEqual(CorreccionEvento.objects.get(marcacion=marca).tipo_evento, "SALIDA_REFRIGERIO")

    def test_clasificar_marcacion_laboral_sin_motivo(self):
        marca = MarcacionBiometrica.objects.get(usuario=self.empleado, tipo_evento="SALIDA")
        self.client.force_login(self.admin)
        respuesta = self.post_jornada(accion="corregir_evento", marcacion_id=marca.pk, tipo_evento="SALIDA_REFRIGERIO")
        self.assertEqual(respuesta.status_code, 302)
        correccion = CorreccionEvento.objects.get(marcacion=marca)
        self.assertEqual(correccion.tipo_evento, "SALIDA_REFRIGERIO")
        self.assertEqual(correccion.responsable, self.admin)
        self.assertEqual(correccion.motivo, "Clasificación de marcación laboral.")

    def test_guardar_todas_las_correcciones_del_dia_y_recalcular(self):
        MarcacionBiometrica.objects.filter(usuario=self.empleado).update(tipo_evento="SIN_CLASIFICAR")
        datos = {"accion": "corregir_eventos"}
        for marca, tipo in zip(MarcacionBiometrica.objects.filter(usuario=self.empleado).order_by("fecha_hora"), ["ENTRADA", "SALIDA_REFRIGERIO", "RETORNO_REFRIGERIO", "SALIDA"]):
            datos[f"evento_{marca.pk}"] = tipo
            datos[f"original_{marca.pk}"] = "SIN_CLASIFICAR"
        self.client.force_login(self.contadora)
        self.assertEqual(self.post_jornada(**datos).status_code, 302)
        self.assertEqual(CorreccionEvento.objects.count(), 4)
        self.resumen.refresh_from_db()
        self.assertEqual(self.resumen.horas_trabajadas, Decimal("8.25"))
        self.assertEqual(self.resumen.horas_extras_25, Decimal("0.25"))
        self.assertFalse(self.resumen.verificado_contabilidad)
        self.assertTrue(detalle_jornada(self.resumen)["completa"])

    def test_correccion_conjunta_rechaza_marcas_de_otro_trabajador(self):
        ajena = MarcacionBiometrica.objects.create(usuario=self.otro, dni=self.otro.dni, fecha_hora=timezone.make_aware(datetime.combine(self.dia, time(9))))
        self.client.force_login(self.contadora)
        self.post_jornada(accion="corregir_eventos", **{f"evento_{ajena.pk}": "SALIDA", f"original_{ajena.pk}": "ENTRADA"})
        self.assertFalse(CorreccionEvento.objects.exists())

    def test_asociacion_conserva_identificador_reportado(self):
        marca = MarcacionBiometrica.objects.create(dni="00000039", fecha_hora=timezone.make_aware(datetime.combine(self.dia, time(7))))
        self.client.force_login(self.admin)
        self.client.post(reverse("asociar_marcacion", args=[marca.pk]), {"usuario": self.empleado.pk, "motivo": "Identidad verificada"})
        marca.refresh_from_db()
        self.assertEqual(marca.usuario, self.empleado)
        self.assertEqual(marca.dni, "00000039")

    def test_exportacion_filtrada_y_neutraliza_formulas(self):
        self.empleado.first_name = "=FORMULA"
        self.empleado.save()
        self.client.force_login(self.contadora)
        res = self.client.get(reverse("exportar_asistencia"), {**self.filtros, "sede": "Chiclayo"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("' =FORMULA".replace("' ", "'"), res.content.decode("utf-8-sig"))
        self.assertNotIn("Persona reservada", res.content.decode("utf-8-sig"))

    def test_cierre_no_ignora_jornadas_ocultas_por_filtros(self):
        revisar(self.resumen, self.contadora, "APROBADO")
        self.client.force_login(self.contadora)
        self.client.post(reverse("cerrar_periodo"), {**self.filtros, "sede": "Chiclayo", "confirmar": "si"})
        self.assertFalse(CierreAsistencia.objects.exists())

    def test_cierre_bloquea_modificaciones_y_guarda_snapshot(self):
        self.resumen_otro.delete()
        revisar(self.resumen, self.contadora, "APROBADO")
        self.client.force_login(self.contadora)
        self.client.post(reverse("cerrar_periodo"), {**self.filtros, "confirmar": "si"})
        cierre = CierreAsistencia.objects.get()
        self.assertEqual(cierre.total_jornadas, 1)
        self.assertEqual(cierre.resumen_cierre[0]["horas_trabajadas"], "8.25")
        self.resumen.horas_trabajadas = Decimal("9")
        with self.assertRaises(ValidationError):
            self.resumen.save()
        with self.assertRaises(ValidationError):
            MarcacionBiometrica.objects.create(usuario=self.empleado, dni=self.empleado.dni, fecha_hora=timezone.make_aware(datetime.combine(self.dia, time(18))))
        self.post_jornada(accion="OBSERVADO", motivo="No debe cambiar")
        self.resumen.refresh_from_db()
        self.assertTrue(self.resumen.verificado_contabilidad)

    def test_cambio_de_datos_exige_nueva_revision(self):
        revisar(self.resumen, self.contadora, "APROBADO")
        self.resumen.horas_trabajadas = Decimal("9")
        self.resumen.save(update_fields=["horas_trabajadas"])
        self.resumen.refresh_from_db()
        self.assertFalse(self.resumen.verificado_contabilidad)

    def test_dashboard_no_crea_marcas_ni_contacta_equipo(self):
        antes = MarcacionBiometrica.objects.count()
        self.client.force_login(self.admin)
        with patch.object(ZKTecoLiveClient, "probar_conexion", side_effect=AssertionError("No debe consultar red")):
            self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertEqual(MarcacionBiometrica.objects.count(), antes)

    def test_desconexion_no_inventa_asistencia(self):
        antes = MarcacionBiometrica.objects.count()
        with patch.object(ZKTecoLiveClient, "probar_conexion", return_value={"conectado": False, "mensaje": "Sin conexión"}):
            info = ZKTecoLiveClient().sincronizar_marcaciones_en_vivo()
        self.assertEqual(info["estado_dispositivo"], "SIN CONEXIÓN")
        self.assertEqual(info["nuevas_marcaciones_sincronizadas"], 0)
        self.assertEqual(MarcacionBiometrica.objects.count(), antes)

    def test_formularios_exigen_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.contadora)
        res = cliente.post(reverse("accion_jornada", args=[self.resumen.pk]), {"accion": "APROBADO"})
        self.assertEqual(res.status_code, 403)

    def test_marcacion_web_usa_la_sesion_y_no_inventa_salida(self):
        self.client.force_login(self.empleado)
        res = self.client.post(reverse("marcar_web"), {"dni": self.empleado.dni, "tipo_evento": "ENTRADA", "origen": "KIOSKO_PIN"}, content_type="application/json")
        self.assertEqual(res.status_code, 200)
        r = ResumenAsistenciaDiaria.objects.get(usuario=self.empleado, fecha=timezone.localdate())
        self.assertIsNotNone(r.primera_entrada)
        self.assertIsNone(r.ultima_salida)
        self.assertFalse(r.verificado_contabilidad)
        ajena = self.client.post(reverse("marcar_web"), {"dni": self.otro.dni, "tipo_evento": "ENTRADA", "origen": "KIOSKO_PIN"}, content_type="application/json")
        self.assertEqual(ajena.status_code, 403)

    def test_ajuste_negativo_no_se_aprueba_si_excede_el_concepto(self):
        self.client.force_login(self.contadora)
        self.post_jornada(accion="ajuste", concepto="horas_extras_25", minutos="-15", motivo="Propuesta de corrección")
        ajuste = AjusteAsistencia.objects.get(resumen=self.resumen)
        self.post_jornada(accion="aprobar_ajuste", registro_id=ajuste.pk)
        ajuste.refresh_from_db()
        self.assertIsNone(ajuste.aprobado_el)

    def test_crear_jornada_y_aprobar_vacaciones_sin_marcas(self):
        self.client.force_login(self.contadora)
        dia = self.dia - timedelta(days=3)
        self.client.post(reverse("crear_jornada"), {"usuario": self.empleado.pk, "fecha": dia.isoformat()})
        r = ResumenAsistenciaDiaria.objects.get(usuario=self.empleado, fecha=dia)
        url = reverse("accion_jornada", args=[r.pk])
        self.client.post(url, {"accion": "incidencia", "tipo": "VACACIONES", "motivo": "Periodo autorizado"})
        i = r.incidencias.get()
        self.client.post(url, {"accion": "aprobar_incidencia", "registro_id": i.pk})
        self.client.post(url, {"accion": "APROBADO"})
        r.refresh_from_db()
        self.assertFalse(r.verificado_contabilidad)
        self.client.post(url, {"accion": "aprobar_dia_situacion", "tipo": "VACACIONES"})
        r.refresh_from_db()
        self.assertEqual(r.estado, "VACACIONES")
        self.assertTrue(r.verificado_contabilidad)
        self.assertEqual(r.horas_trabajadas, 0)

    def test_api_no_expone_jornadas_ajenas_a_boleteria(self):
        from core.security import create_access_token
        token = create_access_token(self.empleado)
        res = self.client.get("/api/asistencia/resumen", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(r["dni"] == self.empleado.dni for r in res.json()))

    def test_reporte_api_incorpora_solo_ajustes_aprobados(self):
        from core.security import create_access_token
        AjusteAsistencia.objects.create(resumen=self.resumen, concepto="horas_extras_25", minutos=15, motivo="Validado", creado_por=self.contadora, aprobado_por=self.contadora, aprobado_el=timezone.now())
        AjusteAsistencia.objects.create(resumen=self.resumen, concepto="horas_extras_25", minutos=90, motivo="Pendiente", creado_por=self.admin)
        token = create_access_token(self.contadora)
        res = self.client.get("/api/asistencia/reporte-planilla", {"fecha_inicio": self.dia.isoformat(), "fecha_fin": self.dia.isoformat()}, HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Decimal(str(res.json()["total_horas_extras_25"])), Decimal("0.25"))

    def test_dashboard_separa_indicadores_y_registro_huellero(self):
        self.client.force_login(self.contadora)
        res = self.client.get(reverse("dashboard"), self.filtros)
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        dashboard = html.split('<div id="view-dashboard"', 1)[1].split('<div id="view-huellero"', 1)[0]
        huellero = html.split('<div id="view-huellero"', 1)[1].split('<div id="view-asistencia"', 1)[0]
        self.assertIn("Dashboard general", dashboard)
        self.assertIn("Pendientes prioritarios", dashboard)
        self.assertIn("Trabajadores del periodo", dashboard)
        self.assertNotIn("Indicadores de próximos sprints", dashboard)
        self.assertNotIn('id="tablaZkLive"', dashboard)
        self.assertNotIn('id="btnSync"', dashboard)
        self.assertIn('id="tablaZkLive"', huellero)
        self.assertIn('id="btnSync"', huellero)
        self.assertNotIn('class="kpi-grid"', huellero)

    def test_huellero_muestra_eventos_sin_agrupar_personas(self):
        ahora = timezone.now()
        for tipo in ["ENTRADA", "SALIDA_REFRIGERIO", "RETORNO_REFRIGERIO", "SALIDA"]:
            MarcacionBiometrica.objects.create(usuario=self.empleado, dni=self.empleado.dni, fecha_hora=ahora, tipo_evento=tipo, origen="ZKTECO_EN_LINEA")
        MarcacionBiometrica.objects.create(usuario=self.empleado, dni=self.empleado.dni, fecha_hora=ahora, origen="KIOSKO_PIN")
        self.client.force_login(self.contadora)
        res = self.client.get(reverse("registros_huellero"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["total"], 4)
        self.assertEqual(len(res.json()["registros"]), 4)
        self.assertEqual(res["Cache-Control"], "no-store")

    def test_huellero_restringe_registros_al_empleado(self):
        ahora = timezone.now()
        for u in [self.empleado, self.otro]:
            MarcacionBiometrica.objects.create(usuario=u, dni=u.dni, fecha_hora=ahora, origen="ZKTECO_EN_LINEA")
        self.client.force_login(self.empleado)
        res = self.client.get(reverse("registros_huellero"))
        self.assertEqual(res.json()["total"], 1)
        self.assertEqual(res.json()["registros"][0]["dni"], self.empleado.dni)

    def test_huellero_consulta_sin_crear_marcas_y_exige_sesion(self):
        res = self.client.get(reverse("registros_huellero"))
        self.assertEqual(res.status_code, 302)
        self.client.force_login(self.contadora)
        antes = MarcacionBiometrica.objects.count()
        with patch.object(ZKTecoLiveClient, "probar_conexion", side_effect=AssertionError("El refresco no debe contactar el reloj")):
            self.assertEqual(self.client.get(reverse("registros_huellero")).status_code, 200)
        self.assertEqual(MarcacionBiometrica.objects.count(), antes)
