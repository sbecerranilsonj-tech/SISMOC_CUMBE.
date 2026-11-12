from datetime import date, datetime, time, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from core.models import Usuario
from asistencia.models import Trabajador, IdentidadBiometrica, MarcacionBiometrica, ResumenAsistenciaDiaria, TurnoHorario, CorreccionEvento, CierreAsistencia
from asistencia.services.transferencia import pasar_a_asistencia
from asistencia.services.revision import detalle_jornada
from asistencia.models import IncidenciaAsistencia


class RevisionPorTrabajadorTests(TestCase):
    def setUp(self):
        self.gestor = Usuario.objects.create_user('revisor_persona', email='revisor@example.invalid', dni='11111111', rol='CONTADORA')
        self.ficha = Trabajador.objects.create(nombre_completo='Jorge Aguilar', dni='87654321', area='Boletería', sede='CAJAMARCA')
        self.identidad = IdentidadBiometrica.objects.create(sede='CAJAMARCA', equipo='1', codigo='13', trabajador=self.ficha, nombre=self.ficha.nombre_completo)
        self.desde = date(2026, 8, 1)
        self.hasta = self.desde + timedelta(days=1)
        self.turno = TurnoHorario.objects.create(nombre='Horario revisión', hora_entrada=time(8), hora_salida=time(17), hora_inicio_refrigerio=time(12), hora_fin_refrigerio=time(13))
        for dia in [self.desde, self.hasta]:
            for hora in [time(8), time(12), time(13), time(17)]:
                MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad, fecha_hora=timezone.make_aware(datetime.combine(dia, hora)), tipo_evento='SIN_CLASIFICAR')
        pasar_a_asistencia([self.ficha.pk], self.desde, self.hasta, self.gestor)
        self.client.force_login(self.gestor)
        self.consulta = {'vista': 'asistencia', 'desde': str(self.desde), 'hasta': str(self.hasta)}

    def datos_revision(self):
        datos = {'desde': str(self.desde), 'hasta': str(self.hasta), 'persona_dni': self.ficha.dni, 'turno': self.turno.pk}
        for indice, marca in enumerate(MarcacionBiometrica.objects.filter(identidad_biometrica=self.identidad).order_by('fecha_hora')):
            datos[f'evento_{marca.pk}'] = ['ENTRADA', 'SALIDA_REFRIGERIO', 'RETORNO_REFRIGERIO', 'SALIDA'][indice % 4]
            datos[f'original_{marca.pk}'] = 'SIN_CLASIFICAR'
        return datos

    def test_lista_una_fila_por_trabajador_y_ventana_con_todas_sus_marcas(self):
        respuesta = self.client.get(reverse('dashboard'), self.consulta)
        self.assertEqual(respuesta.context['total_trabajadores_asistencia'], 1)
        self.assertEqual(respuesta.context['pagina_trabajadores'][0]['jornadas'], 2)
        self.assertContains(respuesta, 'Revisar marcaciones')
        self.assertNotContains(respuesta, 'revision-trabajador-dialog')
        respuesta = self.client.get(reverse('dashboard'), {**self.consulta, 'persona_dni': self.ficha.dni})
        self.assertContains(respuesta, 'id="revision-trabajador-dialog"')
        self.assertEqual(len(respuesta.context['revision_trabajador']['marcas']), 8)
        self.assertEqual(len(respuesta.context['revision_trabajador']['detalles']), 2)
        self.assertContains(respuesta, 'Guardar clasificación y validar jornadas')

    def test_clasificar_actualiza_tiempos_sin_aprobar_y_preserva_original(self):
        res = self.client.post(reverse('validar_marcaciones_trabajador'), self.datos_revision())
        self.assertEqual(res.status_code, 302)
        self.assertIn('persona_dni=87654321', res.url)
        self.assertEqual(CorreccionEvento.objects.count(), 8, [str(m) for m in res.wsgi_request._messages])
        for jornada in ResumenAsistenciaDiaria.objects.all():
            self.assertEqual(jornada.turno_aplicado_id, self.turno.pk)
            self.assertEqual(jornada.horas_trabajadas, 8)
            self.assertEqual(jornada.horas_extras_25, 0)
            self.assertEqual(jornada.estado, 'ASISTIO')
            self.assertFalse(jornada.verificado_contabilidad)
        self.assertFalse(MarcacionBiometrica.objects.exclude(tipo_evento='SIN_CLASIFICAR').exists())
        respuesta = self.client.get(res.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '08:00:00')
        self.assertEqual(respuesta.context['revision_trabajador']['horario_comun_id'], self.turno.pk)
        self.assertNotContains(respuesta, 'name="turno"')  # La asignación se gestiona en Personal y jornadas.

    def test_marca_ajena_cancela_todos_los_cambios(self):
        ajena = MarcacionBiometrica.objects.create(usuario=self.gestor, dni=self.gestor.dni, fecha_hora=timezone.make_aware(datetime.combine(self.desde, time(9))))
        datos = self.datos_revision()
        datos[f'evento_{ajena.pk}'] = 'ENTRADA'
        datos[f'original_{ajena.pk}'] = 'SIN_CLASIFICAR'
        self.client.post(reverse('validar_marcaciones_trabajador'), datos)
        self.assertEqual(CorreccionEvento.objects.count(), 0)

    def test_datos_desactualizados_no_sobrescriben_otra_revision(self):
        datos = self.datos_revision()
        marca = MarcacionBiometrica.objects.order_by('fecha_hora').first()
        CorreccionEvento.objects.create(marcacion=marca, tipo_evento='ENTRADA', motivo='Revisión anterior', responsable=self.gestor)
        self.client.post(reverse('validar_marcaciones_trabajador'), datos)
        self.assertEqual(CorreccionEvento.objects.count(), 1)
        self.assertEqual(CorreccionEvento.objects.get().motivo, 'Revisión anterior')

    def test_periodo_cerrado_no_permite_clasificar(self):
        CierreAsistencia.objects.create(fecha_inicio=self.desde, fecha_fin=self.hasta, total_jornadas=2)
        self.client.post(reverse('validar_marcaciones_trabajador'), self.datos_revision())
        self.assertEqual(CorreccionEvento.objects.count(), 0)
        respuesta = self.client.get(reverse('dashboard'), {**self.consulta, 'persona_dni': self.ficha.dni})
        self.assertContains(respuesta, 'Periodo cerrado')

    def test_empleado_no_ve_otra_persona_y_csrf_es_obligatorio(self):
        seguro = Client(enforce_csrf_checks=True)
        seguro.force_login(self.gestor)
        self.assertEqual(seguro.post(reverse('validar_marcaciones_trabajador'), self.datos_revision()).status_code, 403)
        empleado = Usuario.objects.create_user('empleado_sin_revision', email='empleado@example.invalid', dni='22222222', rol='ADMINISTRATIVO')
        self.client.force_login(empleado)
        self.assertEqual(self.client.get(reverse('dashboard'), {**self.consulta, 'persona_dni': self.ficha.dni}).status_code, 404)
        self.assertEqual(self.client.post(reverse('validar_marcaciones_trabajador'), self.datos_revision()).status_code, 403)

    def test_calendario_incluye_fechas_sin_marcas_sin_crear_jornadas(self):
        consulta = {**self.consulta, 'desde': str(self.desde - timedelta(days=1)), 'hasta': str(self.hasta + timedelta(days=1)), 'persona_dni': self.ficha.dni}
        respuesta = self.client.get(reverse('dashboard'), consulta)
        calendario = respuesta.context['revision_trabajador']['calendario']
        self.assertEqual(len(calendario), 4)
        self.assertIsNone(calendario[0]['detalle'])
        self.assertIsNone(calendario[-1]['detalle'])
        self.assertEqual(ResumenAsistenciaDiaria.objects.count(), 2)
        self.assertContains(respuesta, 'Sin marcaciones')
        self.assertContains(respuesta, 'Feriado no laborado')

    def test_registrar_feriado_y_aprobar_sin_inventar_marcas(self):
        dia = self.hasta + timedelta(days=1)
        datos = {'persona_dni': self.ficha.dni, 'desde': str(self.desde), 'hasta': str(dia), 'fecha': str(dia), 'tipo_dia': 'FERIADO_NO_LABORADO'}
        respuesta = self.client.post(reverse('registrar_dia_sin_marcas'), datos)
        self.assertEqual(respuesta.status_code, 302)
        resumen = ResumenAsistenciaDiaria.objects.get(fecha=dia)
        incidencia = IncidenciaAsistencia.objects.get(resumen=resumen)
        self.assertIsNone(incidencia.aprobado_el)
        self.assertFalse(resumen.verificado_contabilidad)
        self.assertEqual(MarcacionBiometrica.objects.count(), 8)
        self.client.post(reverse('accion_jornada', args=[resumen.pk]), {'accion': 'aprobar_incidencia', 'registro_id': incidencia.pk})
        resumen.refresh_from_db()
        self.assertEqual(resumen.estado, 'FERIADO')
        self.assertEqual(detalle_jornada(resumen)['bloqueos'], [])
        self.assertEqual(resumen.horas_trabajadas, 0)

    def test_no_registrar_descanso_sobre_dia_con_marcas_o_cerrado(self):
        datos = {'persona_dni': self.ficha.dni, 'desde': str(self.desde), 'hasta': str(self.hasta + timedelta(days=1)), 'fecha': str(self.desde), 'tipo_dia': 'DESCANSO_SEMANAL'}
        self.client.post(reverse('registrar_dia_sin_marcas'), datos)
        self.assertEqual(IncidenciaAsistencia.objects.count(), 0)
        dia = self.hasta + timedelta(days=1)
        CierreAsistencia.objects.create(fecha_inicio=dia, fecha_fin=dia, total_jornadas=0)
        self.client.post(reverse('registrar_dia_sin_marcas'), {**datos, 'fecha': str(dia)})
        self.assertEqual(ResumenAsistenciaDiaria.objects.count(), 2)
        self.assertEqual(IncidenciaAsistencia.objects.count(), 0)

    def test_descanso_pendiente_muestra_situacion_sin_detalle_de_marcas(self):
        dia = self.hasta + timedelta(days=1)
        datos = {'persona_dni': self.ficha.dni, 'desde': str(self.desde), 'hasta': str(dia), 'fecha': str(dia), 'tipo_dia': 'DESCANSO_SEMANAL'}
        respuesta = self.client.post(reverse('registrar_dia_sin_marcas'), datos)
        self.assertNotIn('detalle=', respuesta.url)
        resumen = ResumenAsistenciaDiaria.objects.get(fecha=dia)
        detalle = detalle_jornada(resumen)
        self.assertTrue(detalle['solo_situacion'])
        self.assertNotIn('Trabajador sin turno asignado.', detalle['alertas'])
        self.assertEqual(detalle['bloqueos'], ['Apruebe la situación del día registrada.'])
        respuesta = self.client.get(reverse('dashboard'), {**self.consulta, 'hasta': str(dia), 'persona_dni': self.ficha.dni, 'detalle': resumen.pk})
        self.assertTrue(respuesta.context['detalle_jornada']['solo_situacion'])
        self.assertContains(respuesta, 'id="detalle-jornada-dialog"')
        self.assertContains(respuesta, 'day-situation-panel')
        self.assertNotContains(respuesta, 'tabla-control-excel')
        self.assertContains(respuesta, 'Seleccionar situación')

    def test_aprobar_descanso_y_dia_desde_la_fila(self):
        dia = self.hasta + timedelta(days=1)
        self.client.post(reverse('registrar_dia_sin_marcas'), {'persona_dni': self.ficha.dni, 'desde': str(self.desde), 'hasta': str(dia), 'fecha': str(dia), 'tipo_dia': 'DESCANSO_SEMANAL'})
        resumen = ResumenAsistenciaDiaria.objects.get(fecha=dia)
        incidencia = IncidenciaAsistencia.objects.get(resumen=resumen)
        datos = {'persona_dni': self.ficha.dni, 'desde': str(self.desde), 'hasta': str(dia), 'solo_situacion': 'si'}
        respuesta = self.client.post(reverse('accion_jornada', args=[resumen.pk]), {**datos, 'accion': 'aprobar_incidencia', 'registro_id': incidencia.pk})
        self.assertNotIn('detalle=', respuesta.url)
        self.client.post(reverse('accion_jornada', args=[resumen.pk]), {**datos, 'accion': 'aprobar_dia_situacion', 'tipo': 'DESCANSO_SEMANAL'})
        resumen.refresh_from_db()
        self.assertTrue(resumen.verificado_contabilidad)
        self.assertEqual(resumen.estado, 'DIA_LIBRE')
        self.assertEqual(MarcacionBiometrica.objects.count(), 8)

    def test_incidente_no_oculta_marcas_de_una_jornada_laborada(self):
        resumen = ResumenAsistenciaDiaria.objects.order_by('fecha').first()
        IncidenciaAsistencia.objects.create(resumen=resumen, tipo='DESCANSO_SEMANAL', motivo='Revisar situación', creado_por=self.gestor)
        self.assertFalse(detalle_jornada(resumen)['solo_situacion'])

    def crear_dia_pendiente_justificar(self, aprobado=False):
        dia = self.hasta + timedelta(days=1)
        r = ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha, fecha=dia, estado='POR_REVISAR')
        incidencia = IncidenciaAsistencia.objects.create(resumen=r, tipo='OTRO', motivo='Día no trabajado pendiente de justificar', creado_por=self.gestor, aprobado_el=timezone.now() if aprobado else None, aprobado_por=self.gestor if aprobado else None)
        datos = {**self.consulta, 'hasta': str(dia), 'persona_dni': self.ficha.dni, 'solo_situacion': 'si'}
        return r, incidencia, datos

    def test_justificar_dia_antes_aprobado_requiere_nueva_aprobacion(self):
        r, incidencia, datos = self.crear_dia_pendiente_justificar(aprobado=True)
        respuesta = self.client.get(reverse('dashboard'), datos)
        self.assertContains(respuesta, 'Justificación pendiente')
        self.assertContains(respuesta, 'Seleccionar situación')
        self.assertNotContains(respuesta, 'Situación aprobada')
        self.client.post(reverse('accion_jornada', args=[r.pk]), {**datos, 'accion': 'justificar_dia', 'tipo': 'DESCANSO_SEMANAL', 'motivo': 'Descanso según programación'})
        incidencia.refresh_from_db()
        self.assertEqual(incidencia.tipo, 'DESCANSO_SEMANAL')
        self.assertIsNone(incidencia.aprobado_el)
        self.assertTrue(r.historial_revision.filter(detalle__contains='Aprobación anterior:').exists())
        self.client.post(reverse('accion_jornada', args=[r.pk]), {**datos, 'accion': 'APROBADO'})
        r.refresh_from_db()
        self.assertFalse(r.verificado_contabilidad)
        self.client.post(reverse('accion_jornada', args=[r.pk]), {**datos, 'accion': 'aprobar_incidencia', 'registro_id': incidencia.pk})
        self.client.post(reverse('accion_jornada', args=[r.pk]), {**datos, 'accion': 'aprobar_dia_situacion', 'tipo': 'DESCANSO_SEMANAL'})
        r.refresh_from_db()
        self.assertTrue(r.verificado_contabilidad)
        self.assertEqual(r.estado, 'DIA_LIBRE')
        self.assertEqual(MarcacionBiometrica.objects.count(), 8)

    def test_no_se_aprueba_placeholder_sin_justificacion(self):
        r, incidencia, datos = self.crear_dia_pendiente_justificar()
        self.client.post(reverse('accion_jornada', args=[r.pk]), {**datos, 'accion': 'aprobar_incidencia', 'registro_id': incidencia.pk})
        incidencia.refresh_from_db()
        self.assertIsNone(incidencia.aprobado_el)
        self.client.post(reverse('accion_jornada', args=[r.pk]), {**datos, 'accion': 'justificar_dia', 'tipo': 'PERMISO', 'motivo': ''})
        incidencia.refresh_from_db()
        self.assertEqual(incidencia.tipo, 'OTRO')

    def test_justificacion_no_modifica_periodo_cerrado(self):
        r, incidencia, datos = self.crear_dia_pendiente_justificar(aprobado=True)
        CierreAsistencia.objects.create(fecha_inicio=r.fecha, fecha_fin=r.fecha, total_jornadas=1)
        self.client.post(reverse('accion_jornada', args=[r.pk]), {**datos, 'accion': 'justificar_dia', 'tipo': 'PERMISO', 'motivo': 'Autorización'})
        incidencia.refresh_from_db()
        self.assertEqual(incidencia.tipo, 'OTRO')
        self.assertIsNotNone(incidencia.aprobado_el)

    def test_situaciones_excepto_permiso_no_requieren_motivo(self):
        r, incidencia, datos = self.crear_dia_pendiente_justificar()
        for tipo in ['DESCANSO_SEMANAL', 'FERIADO_NO_LABORADO', 'NO_LABORO', 'VACACIONES', 'DESCANSO_MEDICO', 'CAMBIO_DESCANSO']:
            incidencia.tipo = 'OTRO'
            incidencia.motivo = 'Día no trabajado pendiente de justificar'
            incidencia.save()
            self.client.post(reverse('accion_jornada', args=[r.pk]), {**datos, 'accion': 'justificar_dia', 'tipo': tipo})
            incidencia.refresh_from_db()
            self.assertEqual(incidencia.tipo, tipo)
            self.assertEqual(incidencia.motivo, dict(IncidenciaAsistencia.TIPOS)[tipo])
            self.assertIsNone(incidencia.aprobado_el)

    def test_permiso_conserva_justificacion_escrita(self):
        r, incidencia, datos = self.crear_dia_pendiente_justificar()
        self.client.post(reverse('accion_jornada', args=[r.pk]), {**datos, 'accion': 'justificar_dia', 'tipo': 'PERMISO', 'motivo': 'Trámite personal autorizado'})
        incidencia.refresh_from_db()
        self.assertEqual(incidencia.tipo, 'PERMISO')
        self.assertEqual(incidencia.motivo, 'Trámite personal autorizado')
        self.assertIsNone(incidencia.aprobado_el)

    def test_navegacion_siguiente_anterior_trabajadores(self):
        ficha2 = Trabajador.objects.create(nombre_completo='Ana Balarezo', dni='12345678', area='Operaciones', sede='CAJAMARCA')
        id2 = IdentidadBiometrica.objects.create(sede='CAJAMARCA', equipo='1', codigo='14', trabajador=ficha2, nombre=ficha2.nombre_completo)
        MarcacionBiometrica.objects.create(identidad_biometrica=id2, fecha_hora=timezone.make_aware(datetime.combine(self.desde, time(8))), tipo_evento='ENTRADA')
        pasar_a_asistencia([ficha2.pk], self.desde, self.hasta, self.gestor)

        # Ana Balarezo (12345678) es la primera en orden alfabético
        resp_ana = self.client.get(reverse('dashboard'), {**self.consulta, 'persona_dni': ficha2.dni})
        self.assertContains(resp_ana, 'id="revision-trabajador-dialog"')
        rev_ana = resp_ana.context['revision_trabajador']
        self.assertIsNone(rev_ana['anterior_dni'])
        self.assertEqual(rev_ana['siguiente_dni'], self.ficha.dni)
        self.assertEqual(rev_ana['posicion_indice'], 1)
        self.assertEqual(rev_ana['total_trabajadores'], 2)
        self.assertContains(resp_ana, f'persona_dni={self.ficha.dni}')

        # Jorge Aguilar (87654321) es el segundo
        resp_jorge = self.client.get(reverse('dashboard'), {**self.consulta, 'persona_dni': self.ficha.dni})
        rev_jorge = resp_jorge.context['revision_trabajador']
        self.assertEqual(rev_jorge['anterior_dni'], ficha2.dni)
        self.assertIsNone(rev_jorge['siguiente_dni'])
        self.assertEqual(rev_jorge['posicion_indice'], 2)
        self.assertContains(resp_jorge, f'persona_dni={ficha2.dni}')

    def test_navegacion_siguiente_anterior_dias(self):
        jornadas = list(ResumenAsistenciaDiaria.objects.filter(trabajador=self.ficha).order_by('fecha', 'pk'))
        self.assertEqual(len(jornadas), 2)
        j1, j2 = jornadas[0], jornadas[1]

        # Abrir primer día
        resp_dia1 = self.client.get(reverse('dashboard'), {**self.consulta, 'persona_dni': self.ficha.dni, 'detalle': j1.pk})
        det1 = resp_dia1.context['detalle_jornada']
        self.assertIsNone(det1['anterior_pk'])
        self.assertEqual(det1['siguiente_pk'], j2.pk)
        self.assertContains(resp_dia1, f'detalle={j2.pk}')

        # Abrir segundo día
        resp_dia2 = self.client.get(reverse('dashboard'), {**self.consulta, 'persona_dni': self.ficha.dni, 'detalle': j2.pk})
        det2 = resp_dia2.context['detalle_jornada']
        self.assertEqual(det2['anterior_pk'], j1.pk)
        self.assertIsNone(det2['siguiente_pk'])
        self.assertContains(resp_dia2, f'detalle={j1.pk}')

    def test_navegacion_incluye_hueco_y_permite_confirmar_situacion(self):
        j1 = ResumenAsistenciaDiaria.objects.filter(trabajador=self.ficha).earliest('fecha')
        hueco = self.hasta + timedelta(days=1)
        despues = hueco + timedelta(days=1)
        ultimo = ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha, fecha=despues)
        consulta = {**self.consulta, 'hasta': str(despues), 'persona_dni': self.ficha.dni}
        j2 = ResumenAsistenciaDiaria.objects.get(trabajador=self.ficha, fecha=self.hasta)
        respuesta = self.client.get(reverse('dashboard'), {**consulta, 'detalle': j2.pk})
        d = respuesta.context['detalle_jornada']
        self.assertEqual(d['siguiente_fecha'], hueco)
        self.assertIsNone(d['siguiente_pk'])
        self.assertContains(respuesta, 'name="navegar_dia"')
        self.assertFalse(ResumenAsistenciaDiaria.objects.filter(trabajador=self.ficha, fecha=hueco).exists())
        respuesta = self.client.post(reverse('registrar_trabajo_omitido'), {
            **consulta, 'navegar_dia': 'si', 'fecha': str(hueco), 'area': 'Boletería',
        })
        r = ResumenAsistenciaDiaria.objects.get(trabajador=self.ficha, fecha=hueco)
        self.assertIn(f'detalle={r.pk}', respuesta.url)
        self.assertIn('area=', respuesta.url)
        self.assertFalse(r.verificado_contabilidad)
        self.assertEqual(r.marcaciones_publicadas, [])
        respuesta = self.client.get(reverse('dashboard'), {**consulta, 'detalle': r.pk})
        self.assertContains(respuesta, 'Registrar situación')
        self.assertEqual(respuesta.context['detalle_jornada']['siguiente_pk'], ultimo.pk)
        self.assertEqual(respuesta.context['detalle_jornada']['anterior_pk'], j2.pk)
        respuesta = self.client.post(reverse('accion_jornada', args=[r.pk]), {
            **consulta, 'accion': 'aprobar_dia_situacion', 'tipo': 'DESCANSO_SEMANAL',
            'solo_situacion': 'si', 'mantener_detalle': 'si',
        })
        self.assertIn(f'detalle={r.pk}', respuesta.url)
        r.refresh_from_db()
        self.assertTrue(r.verificado_contabilidad)

    def datos_olvido(self):
        return {'persona_dni':self.ficha.dni,'desde':'2026-08-01','hasta':'2026-08-10',
            'fecha':'2026-08-05','entrada_olvido':'2026-08-05T08:00',
            'inicio_refrigerio_olvido':'2026-08-05T12:00','fin_refrigerio_olvido':'2026-08-05T13:00',
            'salida_olvido':'2026-08-05T17:00','motivo_olvido':'Olvidó marcar; horas confirmadas con supervisora.'}

    def test_registrar_trabajo_omitido_crea_marcas_manuales_sin_aprobar(self):
        res=self.client.post(reverse('registrar_trabajo_omitido'),self.datos_olvido())
        self.assertEqual(res.status_code,302)
        r=ResumenAsistenciaDiaria.objects.get(fecha=date(2026,8,5))
        marcas=MarcacionBiometrica.objects.filter(pk__in=r.marcaciones_publicadas).order_by('fecha_hora')
        self.assertEqual(list(marcas.values_list('tipo_evento',flat=True)),['ENTRADA','SALIDA_REFRIGERIO','RETORNO_REFRIGERIO','SALIDA'])
        self.assertTrue(all(m.origen=='SISTEMA_MANUAL' and m.registrada_por==self.gestor for m in marcas))
        self.assertFalse(r.verificado_contabilidad)
        self.assertEqual(r.horas_trabajadas,8)
        self.assertEqual(r.estado_revision,'PENDIENTE')
        self.client.post(reverse('registrar_trabajo_omitido'),self.datos_olvido())
        self.assertEqual(MarcacionBiometrica.objects.filter(pk__in=r.marcaciones_publicadas).count(),4)

    def test_trabajo_omitido_reemplaza_situacion_con_historial(self):
        r=ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha,fecha=date(2026,8,5),estado='PERMISO')
        IncidenciaAsistencia.objects.create(resumen=r,tipo='PERMISO',motivo='Motivo anterior',creado_por=self.gestor)
        self.client.post(reverse('registrar_trabajo_omitido'),self.datos_olvido())
        r.refresh_from_db()
        self.assertFalse(r.incidencias.exists())
        self.assertTrue(r.historial_revision.filter(detalle__contains='Motivo anterior').exists())
        self.assertFalse(r.verificado_contabilidad)
        self.assertEqual(len(r.marcaciones_publicadas),4)

    def test_trabajo_omitido_error_revierte_toda_la_jornada(self):
        for cambios in [{'motivo_olvido':''},{'salida_olvido':'2026-08-05T07:00'},
                        {'fin_refrigerio_olvido':''}]:
            self.client.post(reverse('registrar_trabajo_omitido'),{**self.datos_olvido(),**cambios})
            self.assertFalse(ResumenAsistenciaDiaria.objects.filter(fecha=date(2026,8,5)).exists())
        self.assertEqual(MarcacionBiometrica.objects.count(),8)

    def test_trabajo_omitido_respeta_cierre_y_aprobacion(self):
        r=ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha,fecha=date(2026,8,5),verificado_contabilidad=True,estado_revision='APROBADO')
        self.client.post(reverse('registrar_trabajo_omitido'),self.datos_olvido())
        r.refresh_from_db()
        self.assertTrue(r.verificado_contabilidad)
        self.assertEqual(MarcacionBiometrica.objects.count(),8)
        CierreAsistencia.objects.create(fecha_inicio=r.fecha,fecha_fin=r.fecha,total_jornadas=1)
        self.client.post(reverse('registrar_trabajo_omitido'),self.datos_olvido())
        self.assertEqual(MarcacionBiometrica.objects.count(),8)

    def test_trabajo_omitido_admite_salida_al_dia_siguiente(self):
        datos={**self.datos_olvido(),'entrada_olvido':'2026-08-05T20:00',
            'inicio_refrigerio_olvido':'2026-08-05T23:00','fin_refrigerio_olvido':'2026-08-06T00:00',
            'salida_olvido':'2026-08-06T07:00'}
        self.client.post(reverse('registrar_trabajo_omitido'),datos)
        r=ResumenAsistenciaDiaria.objects.get(fecha=date(2026,8,5))
        self.assertEqual(r.horas_trabajadas,10)
        self.assertEqual(len(r.marcaciones_publicadas),4)

    def test_trabajo_sin_marcar_abre_el_mismo_detalle_vacio(self):
        datos={**self.datos_olvido(),'abrir_detalle':'si'}
        respuesta=self.client.post(reverse('registrar_trabajo_omitido'),datos)
        self.assertEqual(respuesta.status_code,302)
        r=ResumenAsistenciaDiaria.objects.get(fecha=date(2026,8,5))
        self.assertIn('detalle='+str(r.pk),respuesta.url)
        self.assertEqual(r.marcaciones_publicadas,[])
        self.assertFalse(r.verificado_contabilidad)
        self.assertEqual(MarcacionBiometrica.objects.count(),8)
        pantalla=self.client.get(respuesta.url)
        self.assertContains(pantalla,'Control diario')
        self.assertContains(pantalla,'Agregar marcación manual')
        self.assertContains(pantalla,'tabla-control-excel')
        self.assertNotContains(pantalla,'id="trabajo-omitido-dialog"')
        self.client.post(reverse('accion_jornada',args=[r.pk]),{'accion':'marcacion_manual',
            'fecha_manual':'2026-08-05','hora_manual':'08:00','tipo_evento_manual':'ENTRADA',
            'motivo_manual':'Olvido confirmado por la supervisora'})
        r.refresh_from_db()
        self.assertEqual(len(r.marcaciones_publicadas),1)
        self.assertFalse(r.verificado_contabilidad)

    def test_navegar_descanso_y_aprobar_conserva_detalle_y_dia_siguiente(self):
        descanso=self.hasta+timedelta(days=1)
        siguiente=descanso+timedelta(days=1)
        r=ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha,fecha=descanso,estado='DIA_LIBRE')
        IncidenciaAsistencia.objects.create(resumen=r,tipo='DESCANSO_SEMANAL',motivo='Descanso del martes',creado_por=self.gestor)
        ultimo=ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha,fecha=siguiente)
        consulta={'vista':'asistencia','desde':str(self.desde),'hasta':str(siguiente),'persona_dni':self.ficha.dni,'detalle':r.pk}
        res=self.client.get(reverse('dashboard'),consulta)
        d=res.context['detalle_jornada']
        self.assertEqual(d['resumen'].pk,r.pk)
        self.assertEqual(d['siguiente_pk'],ultimo.pk)
        self.assertEqual(d['anterior_fecha'],self.hasta)
        self.assertContains(res,'Descanso del martes')
        post=self.client.post(reverse('accion_jornada',args=[r.pk]),{'accion':'aprobar_dia_situacion',
            'tipo':'DESCANSO_SEMANAL','solo_situacion':'si','mantener_detalle':'si',
            'persona_dni':self.ficha.dni,'desde':str(self.desde),'hasta':str(siguiente)})
        self.assertIn('detalle='+str(r.pk),post.url)
        r.refresh_from_db()
        self.assertTrue(r.verificado_contabilidad)

    def test_detalle_no_renderiza_revision_completa_y_reutiliza_marcas(self):
        from unittest.mock import patch
        from asistencia.services.revision_trabajador import detalles_en_lote
        jornada=ResumenAsistenciaDiaria.objects.filter(trabajador=self.ficha).first()
        otra=Trabajador.objects.create(nombre_completo='Otra persona',dni='55556666',area='Boletería',sede='CAJAMARCA')
        ResumenAsistenciaDiaria.objects.create(trabajador=otra,fecha=self.desde)
        with patch('asistencia.services.revision_trabajador.detalles_en_lote',wraps=detalles_en_lote) as lote:
            respuesta=self.client.get(reverse('dashboard'),dict(self.consulta,detalle=jornada.pk,persona_dni=self.ficha.dni))
        self.assertEqual(respuesta.status_code,200)
        self.assertContains(respuesta,'id="detalle-jornada-dialog"')
        self.assertNotContains(respuesta,'id="revision-trabajador-dialog"')
        self.assertFalse(lote.called)
        for llamada in lote.call_args_list:
            self.assertTrue(all(r.trabajador_id==self.ficha.pk for r in llamada.args[0]))
        self.assertNotIn('marcas',respuesta.context['revision_trabajador'])
