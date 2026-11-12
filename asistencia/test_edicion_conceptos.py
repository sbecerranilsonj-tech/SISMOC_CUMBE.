from decimal import Decimal
from django.core.exceptions import ValidationError
from asistencia.test_revision_trabajador import RevisionPorTrabajadorTests
from asistencia.models import ResumenAsistenciaDiaria
from asistencia.services.edicion_conceptos import guardar_conceptos
from asistencia.services.revision import valores_ajustados


class EdicionConceptosTests(RevisionPorTrabajadorTests):
    def test_guardar_todas_conserva_tiempos_editados_y_muestra_restaurar(self):
        from django.urls import reverse
        self.client.post(reverse('validar_marcaciones_trabajador'), self.datos_revision())
        r = ResumenAsistenciaDiaria.objects.first()
        from asistencia.models import MarcacionBiometrica
        datos = {'accion':'corregir_eventos','editar_tiempos':'si','jornada_base':'08:00:00','horas_extras_25':'00:20:00','horas_extras_35':'00:25:00','horas_nocturnas':'01:00:00'}
        for m in MarcacionBiometrica.objects.filter(fecha_hora__date=r.fecha).select_related('correccion_evento'):
            datos[f'evento_{m.pk}'] = m.correccion_evento.tipo_evento
            datos[f'original_{m.pk}'] = m.correccion_evento.tipo_evento
        self.client.post(reverse('accion_jornada',args=[r.pk]),datos)
        r.refresh_from_db()
        self.assertEqual(r.conceptos_editados['horas_extras_35'],1500)
        res = self.client.get(reverse('dashboard'), {**self.consulta,'persona_dni':self.ficha.dni,'detalle':r.pk})
        self.assertContains(res,'00:25:00')
        self.assertContains(res,'id="restaurar-conceptos"')
        self.assertContains(res,'form="correcciones-diarias"')
        self.client.post(reverse('accion_jornada',args=[r.pk]),{'accion':'restaurar_conceptos'})
        r.refresh_from_db()
        self.assertEqual(r.conceptos_editados,{})

    def test_guardar_base_sin_indicador_oculto_conserva_valor_al_reabrir(self):
        from django.urls import reverse
        from asistencia.models import MarcacionBiometrica
        from asistencia.services.revision import detalle_jornada
        self.client.post(reverse('validar_marcaciones_trabajador'), self.datos_revision())
        r = ResumenAsistenciaDiaria.objects.first()
        datos = {'accion': 'corregir_eventos', 'jornada_base': '07:00:00',
                 'horas_extras_25': '00:00:00', 'horas_extras_35': '00:00:00',
                 'horas_nocturnas': '00:00:00'}
        for m in MarcacionBiometrica.objects.filter(fecha_hora__date=r.fecha).select_related('correccion_evento'):
            datos[f'evento_{m.pk}'] = m.correccion_evento.tipo_evento
            datos[f'original_{m.pk}'] = m.correccion_evento.tipo_evento
        self.client.post(reverse('accion_jornada', args=[r.pk]), datos)
        r.refresh_from_db()
        self.assertEqual(r.conceptos_editados['jornada_base'], 25200)
        self.assertEqual(detalle_jornada(r)['cuadro_excel']['totales']['saldo'], '01:00:00')
        response = self.client.get(reverse('dashboard'), {**self.consulta, 'persona_dni': self.ficha.dni, 'detalle': r.pk})
        self.assertContains(response, '07:00:00')

    def test_base_cero_conserva_todo_el_trabajo_como_saldo(self):
        from django.urls import reverse
        from asistencia.services.revision import detalle_jornada
        self.client.post(reverse('validar_marcaciones_trabajador'), self.datos_revision())
        r = ResumenAsistenciaDiaria.objects.first()
        totales = detalle_jornada(r)['cuadro_excel']['totales']
        datos = {'accion': 'editar_conceptos', 'jornada_base': '00:00:00',
                 'horas_extras_25': totales['he25'], 'horas_extras_35': totales['he35'],
                 'horas_nocturnas': totales['nocturnas']}
        self.client.post(reverse('accion_jornada', args=[r.pk]), datos)
        r.refresh_from_db()
        self.assertEqual(r.conceptos_editados['jornada_base'], 0)
        nuevos = detalle_jornada(r)['cuadro_excel']['totales']
        self.assertEqual(nuevos['base'], '00:00:00')
        self.assertEqual(nuevos['saldo'], nuevos['trabajo'])
        self.assertFalse(nuevos['es_deficit'])
        self.assertEqual(nuevos['he25'], '02:00:00')
        self.assertEqual(nuevos['he35'], '06:00:00')

    def test_varios_ingresos_suman_tramos_con_una_base_de_ocho_horas(self):
        from datetime import datetime, time
        from django.utils import timezone
        from django.urls import reverse
        from asistencia.models import MarcacionBiometrica
        from asistencia.services.revision import detalle_jornada
        self.client.post(reverse('validar_marcaciones_trabajador'), self.datos_revision())
        r = ResumenAsistenciaDiaria.objects.first()
        originales = detalle_jornada(r)['marcas']
        original = originales[0]
        r.marcaciones_publicadas = [m.pk for m in originales]
        for hora, evento in [(time(20), 'ENTRADA'), (time(23), 'SALIDA')]:
            marca = MarcacionBiometrica.objects.create(
                identidad_biometrica=original.identidad_biometrica,
                fecha_hora=timezone.make_aware(datetime.combine(r.fecha, hora)),
                tipo_evento=evento)
            r.marcaciones_publicadas.append(marca.pk)
        r.ultima_salida = time(23)
        r.save()
        d = detalle_jornada(r)
        self.assertTrue(d['completa'])
        self.assertEqual(d['cuadro_excel']['totales']['base'], '08:00:00')
        self.assertEqual(d['cuadro_excel']['totales']['trabajo'], '11:00:00')
        self.assertEqual(d['cuadro_excel']['totales']['saldo'], '03:00:00')
        self.assertEqual(d['cuadro_excel']['totales']['he25'], '02:00:00')
        self.assertEqual(d['cuadro_excel']['totales']['he35'], '01:00:00')
        marca.tipo_evento = 'SIN_CLASIFICAR'
        marca.save()
        r = ResumenAsistenciaDiaria.objects.get(pk=r.pk)
        self.assertFalse(detalle_jornada(r)['completa'])

    def test_observacion_del_dia_persiste_sin_cambiar_calculos_o_aprobacion(self):
        from django.urls import reverse
        r = ResumenAsistenciaDiaria.objects.first()
        antes = (r.estado_revision, r.verificado_contabilidad, r.horas_trabajadas, r.conceptos_editados)
        texto = 'Reemplazó a un compañero durante una emergencia.'
        self.client.post(reverse('accion_jornada', args=[r.pk]), {'accion': 'observacion_dia', 'observacion_dia': texto})
        r.refresh_from_db()
        self.assertEqual(r.observacion_dia, texto)
        self.assertEqual((r.estado_revision, r.verificado_contabilidad, r.horas_trabajadas, r.conceptos_editados), antes)
        response = self.client.get(reverse('dashboard'), {**self.consulta, 'persona_dni': self.ficha.dni, 'detalle': r.pk})
        self.assertContains(response, texto)
        self.client.post(reverse('accion_jornada', args=[r.pk]), {'accion': 'observacion_dia', 'observacion_dia': ''})
        r.refresh_from_db()
        self.assertEqual(r.observacion_dia, '')

    def test_editar_base_y_restaurar_calculo(self):
        from django.urls import reverse
        from asistencia.services.revision import detalle_jornada
        self.client.post(reverse('validar_marcaciones_trabajador'), self.datos_revision())
        r = ResumenAsistenciaDiaria.objects.first()
        url = reverse('accion_jornada', args=[r.pk])
        datos = {'accion':'editar_conceptos', 'jornada_base':'07:00:00', 'horas_extras_25':'00:45:00', 'horas_extras_35':'00:00:00', 'horas_nocturnas':'00:00:00'}
        self.assertEqual(self.client.post(url,datos).status_code,302)
        r.refresh_from_db()
        d = detalle_jornada(r)
        self.assertEqual(d['cuadro_excel']['totales']['base'],'07:00:00')
        self.assertEqual(d['cuadro_excel']['totales']['saldo'],'01:00:00')
        self.assertEqual(d['cuadro_excel']['totales']['he25'],'00:45:00')
        self.client.post(url,{'accion':'restaurar_conceptos'})
        r.refresh_from_db()
        self.assertEqual(r.conceptos_editados,{})
        self.assertEqual(detalle_jornada(r)['cuadro_excel']['totales']['base'],'08:00:00')
        self.assertEqual(valores_ajustados(r)['horas_extras_25'],0)

    def test_edicion_persiste_y_consolida_sin_cambiar_calculo(self):
        r = ResumenAsistenciaDiaria.objects.first()
        originales = (r.horas_extras_25, r.horas_nocturnas)
        datos = {'horas_extras_25': '00:20:00', 'horas_extras_35': '00:00:00', 'horas_nocturnas': '01:00:30'}
        guardar_conceptos(r, datos, self.gestor)
        r.refresh_from_db()
        self.assertEqual(r.conceptos_editados['horas_nocturnas'], 3630)
        self.assertEqual(valores_ajustados(r)['horas_extras_25'], Decimal(1)/3)
        self.assertEqual((r.horas_extras_25, r.horas_nocturnas), originales)
        self.assertFalse(r.verificado_contabilidad)
        with self.assertRaises(ValidationError):
            guardar_conceptos(r, {**datos, 'horas_extras_25': '-1:00:00'}, self.gestor)
        r.verificado_contabilidad = True
        with self.assertRaises(ValidationError):
            guardar_conceptos(r, datos, self.gestor)
