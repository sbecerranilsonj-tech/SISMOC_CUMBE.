from datetime import date, datetime, time
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from core.models import Usuario
from asistencia.models import Trabajador, IdentidadBiometrica, MarcacionBiometrica, ResumenAsistenciaDiaria, TurnoHorario, CierreAsistencia, CorreccionEvento
from asistencia.services.revision import detalle_jornada


class MarcacionManualTests(TestCase):
    def setUp(self):
        self.contadora = Usuario.objects.create_user('contadora_manual', email='contadora@example.invalid', dni='11111111', rol='CONTADORA')
        self.ficha = Trabajador.objects.create(nombre_completo='Abisag Salazar', dni='87654328', area='Boletería', sede='CAJAMARCA')
        self.identidad = IdentidadBiometrica.objects.create(sede='CAJAMARCA', equipo='1', codigo='42', trabajador=self.ficha)
        self.dia = date(2026, 8, 22)
        turno = TurnoHorario.objects.create(nombre='Mañana Cajamarca', hora_entrada=time(6), hora_salida=time(15))
        self.resumen = ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha, fecha=self.dia, primera_entrada=time(6, 4, 29), ultima_salida=time(14, 47, 14), turno_aplicado=turno, estado='POR_REVISAR')
        self.marcas = []
        for hora, tipo in [(time(6, 4, 29), 'ENTRADA'), (time(8, 21, 37), 'SALIDA_REFRIGERIO'), (time(14, 47, 14), 'RETORNO_REFRIGERIO')]:
            self.marcas.append(MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad, fecha_hora=timezone.make_aware(datetime.combine(self.dia, hora)), tipo_evento=tipo, origen='EXCEL_ZKTECO'))
        self.url = reverse('accion_jornada', args=[self.resumen.pk])
        self.datos = {'accion': 'marcacion_manual', 'fecha_manual': str(self.dia), 'hora_manual': '09:05:00', 'tipo_evento_manual': 'RETORNO_REFRIGERIO', 'identidad_manual': self.identidad.pk, 'motivo_manual': 'Retorno confirmado con el control de la contadora', 'evidencia_manual_url': 'https://example.invalid/control'}
        self.client.force_login(self.contadora)

    def test_agregar_faltante_y_guardar_clasificacion_sin_alterar_originales(self):
        ultima = self.marcas[-1]
        datos = {**self.datos, f'evento_{ultima.pk}': 'SALIDA', f'original_{ultima.pk}': 'RETORNO_REFRIGERIO'}
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 302)
        manual = MarcacionBiometrica.objects.get(origen='SISTEMA_MANUAL')
        self.assertEqual(manual.registrada_por, self.contadora)
        self.assertEqual(manual.identidad_biometrica, self.identidad)
        self.assertIsNone(manual.carga_origen_id)
        self.assertEqual(manual.verificacion_reportada, '')
        self.assertEqual(manual.motivo_manual, self.datos['motivo_manual'])
        self.assertEqual(Usuario.objects.count(), 1)
        for original in self.marcas:
            original.refresh_from_db()
            self.assertEqual(original.origen, 'EXCEL_ZKTECO')
        ultima.refresh_from_db()
        self.assertEqual(ultima.tipo_evento, 'RETORNO_REFRIGERIO')
        self.resumen.refresh_from_db()
        detalle = detalle_jornada(self.resumen)
        self.assertTrue(detalle['completa'])
        self.assertEqual(detalle['trabajo_reconstruido'], '07:59:22')
        self.assertEqual(detalle['refrigerio'], '00:43:23')
        self.assertEqual(self.resumen.horas_trabajadas, Decimal('7.99'))
        self.assertFalse(self.resumen.verificado_contabilidad)
        self.assertTrue(self.resumen.historial_revision.filter(accion='Marcación manual agregada').exists())
        respuesta = self.client.get(reverse('dashboard'), {'vista': 'asistencia', 'desde': str(self.dia), 'hasta': str(self.dia), 'detalle': self.resumen.pk})
        self.assertContains(respuesta, 'Registro manual')
        self.assertContains(respuesta, 'Agregar marcación manual')

    def test_no_repetir_ni_registrar_hora_ajena_a_la_jornada(self):
        self.client.post(self.url, self.datos)
        self.client.post(self.url, self.datos)
        self.assertEqual(MarcacionBiometrica.objects.filter(origen='SISTEMA_MANUAL').count(), 1)
        self.client.post(self.url, {**self.datos, 'fecha_manual': '2026-08-25'})
        self.assertEqual(MarcacionBiometrica.objects.count(), 4)

    def test_dato_manual_invalido_revierte_correcciones_del_mismo_envio(self):
        ultima = self.marcas[-1]
        self.client.post(self.url, {**self.datos, 'hora_manual': 'hora inválida', f'evento_{ultima.pk}': 'SALIDA', f'original_{ultima.pk}': 'RETORNO_REFRIGERIO'})
        self.assertFalse(CorreccionEvento.objects.exists())
        self.assertEqual(MarcacionBiometrica.objects.count(), 3)

    def test_no_aceptar_codigo_de_otro_trabajador(self):
        otra = IdentidadBiometrica.objects.create(sede='TRUJILLO', equipo='1', codigo='42')
        self.client.post(self.url, {**self.datos, 'identidad_manual': otra.pk})
        self.assertEqual(MarcacionBiometrica.objects.count(), 3)

    def test_entrada_o_salida_faltante_amplia_intervalo_guardado(self):
        self.client.post(self.url, {**self.datos, 'hora_manual': '15:00:00', 'tipo_evento_manual': 'SALIDA'})
        self.resumen.refresh_from_db()
        self.assertEqual(self.resumen.ultima_salida, time(15))
        self.assertEqual(len(detalle_jornada(self.resumen)['marcas']), 4)

    def test_respeta_cierre_permisos_y_csrf(self):
        seguro = Client(enforce_csrf_checks=True)
        seguro.force_login(self.contadora)
        self.assertEqual(seguro.post(self.url, self.datos).status_code, 403)
        CierreAsistencia.objects.create(fecha_inicio=self.dia, fecha_fin=self.dia, total_jornadas=1)
        self.client.post(self.url, self.datos)
        self.assertEqual(MarcacionBiometrica.objects.count(), 3)
        self.contadora.rol = 'ADMINISTRATIVO'
        self.contadora.save()
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 403)

    def test_registro_sin_elegir_codigo_ni_enlace(self):
        datos = {k: v for k, v in self.datos.items() if k not in {'identidad_manual', 'evidencia_manual_url'}}
        self.client.post(self.url, datos)
        marca = MarcacionBiometrica.objects.get(origen='SISTEMA_MANUAL')
        self.assertEqual(marca.identidad_biometrica, self.identidad)
        self.assertEqual(marca.evidencia_manual_url, '')

    def test_codigo_automatico_procede_de_las_marcas_de_ese_dia(self):
        IdentidadBiometrica.objects.create(sede='CHICLAYO', equipo='2', codigo='99', trabajador=self.ficha)
        datos = {k: v for k, v in self.datos.items() if k not in {'identidad_manual', 'evidencia_manual_url'}}
        self.client.post(self.url, datos)
        marca = MarcacionBiometrica.objects.get(origen='SISTEMA_MANUAL')
        self.assertEqual(marca.identidad_biometrica, self.identidad)

    def test_eliminar_marcacion_manual_por_error(self):
        # 1. Registrar una marca manual
        self.client.post(self.url, self.datos)
        marca_manual = MarcacionBiometrica.objects.get(origen='SISTEMA_MANUAL')
        self.assertEqual(MarcacionBiometrica.objects.count(), 4)

        # 2. Eliminar la marca manual añadida por error
        res = self.client.post(self.url, {
            'accion': 'eliminar_marcacion_manual',
            'marcacion_id': marca_manual.pk,
        })
        self.assertEqual(res.status_code, 302)
        self.assertFalse(MarcacionBiometrica.objects.filter(pk=marca_manual.pk).exists())
        self.assertEqual(MarcacionBiometrica.objects.count(), 3)
        self.resumen.refresh_from_db()
        self.assertEqual(self.resumen.estado_revision, 'PENDIENTE')

    def test_editar_manual_conserva_id_y_audita_hora_anterior(self):
        self.client.post(self.url,self.datos)
        manual=MarcacionBiometrica.objects.get(origen='SISTEMA_MANUAL')
        respuesta=self.client.post(self.url,{**self.datos,'accion':'editar_marcacion_manual',
            'marcacion_id':manual.pk,'hora_manual':'09:10:00','motivo_manual':'Hora corregida con supervisora'})
        self.assertEqual(respuesta.status_code,302)
        manual.refresh_from_db()
        self.assertEqual(timezone.localtime(manual.fecha_hora).time(),time(9,10))
        self.assertEqual(MarcacionBiometrica.objects.filter(origen='SISTEMA_MANUAL').count(),1)
        self.assertEqual(manual.motivo_manual,'Hora corregida con supervisora')
        self.assertTrue(self.resumen.historial_revision.filter(accion='Marcación manual editada',detalle__contains='09:05').exists())
        self.resumen.refresh_from_db()
        self.assertFalse(self.resumen.verificado_contabilidad)

    def test_editar_rechaza_importada_y_hora_duplicada(self):
        original=self.marcas[0]
        self.client.post(self.url,{**self.datos,'accion':'editar_marcacion_manual','marcacion_id':original.pk})
        original.refresh_from_db()
        self.assertEqual(timezone.localtime(original.fecha_hora).time(),time(6,4,29))
        self.client.post(self.url,self.datos)
        manual=MarcacionBiometrica.objects.get(origen='SISTEMA_MANUAL')
        self.client.post(self.url,{**self.datos,'accion':'editar_marcacion_manual','marcacion_id':manual.pk,'hora_manual':'08:21:37'})
        manual.refresh_from_db()
        self.assertEqual(timezone.localtime(manual.fecha_hora).time(),time(9,5))

    def test_mismo_codigo_en_dos_equipos_guarda_manual_sin_elegir_identidad(self):
        otra=IdentidadBiometrica.objects.create(trabajador=self.ficha,sede='CAJAMARCA',equipo='104',codigo='42')
        self.marcas[1].identidad_biometrica=otra
        self.marcas[1].save(update_fields=['identidad_biometrica'])
        datos={k:v for k,v in self.datos.items() if k not in {'identidad_manual','evidencia_manual_url','motivo_manual'}}
        respuesta=self.client.post(self.url,datos)
        self.assertEqual(respuesta.status_code,302)
        manual=MarcacionBiometrica.objects.get(origen='SISTEMA_MANUAL')
        self.assertEqual(manual.identidad_biometrica.codigo,'42')
        self.assertEqual(manual.identidad_biometrica.trabajador_id,self.ficha.pk)
        self.assertEqual(manual.motivo_manual,'')

    def test_codigos_diferentes_en_la_misma_jornada_no_se_eligen_silenciosamente(self):
        from asistencia.forms import MarcacionManualForm
        otra=IdentidadBiometrica.objects.create(trabajador=self.ficha,sede='CAJAMARCA',equipo='104',codigo='99')
        self.marcas[1].identidad_biometrica=otra
        self.marcas[1].save(update_fields=['identidad_biometrica'])
        datos={k:v for k,v in self.datos.items() if k!='identidad_manual'}
        formulario=MarcacionManualForm(datos,resumen=self.resumen)
        self.assertFalse(formulario.is_valid())
        self.assertIn('identidad_manual',formulario.errors)

    def test_salida_nocturna_requiere_fecha_siguiente_y_se_guarda(self):
        from asistencia.services.marcacion_manual import agregar_marcacion_manual
        from django.core.exceptions import ValidationError
        from datetime import timedelta
        MarcacionBiometrica.objects.filter(identidad_biometrica=self.identidad).delete()
        turno=TurnoHorario.objects.create(nombre='Noche',hora_entrada=time(20),hora_salida=time(7))
        r=self.resumen;r.turno_aplicado=turno;r.primera_entrada=time(20);r.ultima_salida=None;r.save()
        MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad,fecha_hora=timezone.make_aware(datetime.combine(self.dia,time(20))),tipo_evento='ENTRADA')
        datos={'fecha_manual':str(self.dia),'hora_manual':'07:00:00','tipo_evento_manual':'SALIDA'}
        with self.assertRaisesMessage(ValidationError,'día siguiente'):
            agregar_marcacion_manual(r,datos,self.contadora)
        self.assertFalse(MarcacionBiometrica.objects.filter(origen='SISTEMA_MANUAL').exists())
        datos['fecha_manual']=str(self.dia+timedelta(days=1))
        m=agregar_marcacion_manual(r,datos,self.contadora)
        self.assertEqual(timezone.localtime(m.fecha_hora).date(),self.dia+timedelta(days=1))
        r.refresh_from_db()
        self.assertTrue(detalle_jornada(r)['completa'])

    def test_madrugada_manual_no_bloqueada_por_jornada_siguiente_vacia(self):
        from datetime import timedelta
        self.marcas[0].fecha_hora = timezone.make_aware(datetime.combine(self.dia, time(21)))
        self.marcas[0].save()
        manana = self.dia + timedelta(days=1)
        for marca, hora, evento in [(self.marcas[1], time(1, 12), 'SALIDA_REFRIGERIO'), (self.marcas[2], time(7), 'SALIDA')]:
            marca.fecha_hora = timezone.make_aware(datetime.combine(manana, hora))
            marca.tipo_evento = evento
            marca.save()
        turno = TurnoHorario.objects.create(nombre='Noche manual', hora_entrada=time(20), hora_salida=time(7))
        self.resumen.turno_aplicado = turno
        self.resumen.primera_entrada = time(21)
        self.resumen.ultima_salida = time(7)
        self.resumen.marcaciones_publicadas = [m.pk for m in self.marcas]
        self.resumen.save()
        ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha, fecha=manana, turno_aplicado=turno, marcaciones_publicadas=[])
        self.client.post(self.url, {**self.datos, 'fecha_manual': str(manana), 'hora_manual': '01:57:00'})
        self.assertTrue(MarcacionBiometrica.objects.filter(origen='SISTEMA_MANUAL', tipo_evento='RETORNO_REFRIGERIO').exists())
        self.resumen.refresh_from_db()
        self.assertTrue(detalle_jornada(self.resumen)['completa'])
