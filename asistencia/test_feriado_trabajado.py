from datetime import date
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.urls import reverse
from asistencia import test_reglas_jornada as fixtures
from asistencia.models import AjusteAsistencia, CierreAsistencia
from asistencia.services.feriado_trabajado import confirmar_feriado_trabajado
from asistencia.services.revision import detalle_jornada


class FeriadoTrabajadoTests(TestCase):
    setUp = fixtures.ReglasJornadaTests.setUp
    jornada = fixtures.ReglasJornadaTests.jornada

    def test_registra_ocho_horas_sin_alterar_extras_ni_aprobar_dia(self):
        r = self.jornada(date(2026, 8, 6), refrigerio=True)
        antes = detalle_jornada(r)['cuadro_excel']['totales']
        self.assertTrue(detalle_jornada(r)['cuadro_excel']['puede_confirmar_feriado'])
        ajuste = confirmar_feriado_trabajado(r, self.actor)
        r.refresh_from_db()
        despues = detalle_jornada(r)['cuadro_excel']['totales']
        self.assertEqual(ajuste.minutos, 480)
        self.assertEqual(ajuste.aprobado_por, self.actor)
        self.assertEqual(despues['feriado'], '08:00:00')
        for campo in ['trabajo', 'he25', 'he35']:
            self.assertEqual(antes[campo], despues[campo])
        self.assertFalse(r.verificado_contabilidad)
        self.assertFalse(detalle_jornada(r)['cuadro_excel']['puede_confirmar_feriado'])
        with self.assertRaises(ValidationError):
            confirmar_feriado_trabajado(r, self.actor)
        self.assertEqual(AjusteAsistencia.objects.count(), 1)

    def test_rechaza_sin_marcas_y_dia_ordinario(self):
        r = self.jornada(date(2026, 8, 6), marcas=False)
        with self.assertRaises(ValidationError): confirmar_feriado_trabajado(r, self.actor)
        r = self.jornada(date(2026, 8, 7))
        with self.assertRaises(ValidationError): confirmar_feriado_trabajado(r, self.actor)
        self.assertFalse(AjusteAsistencia.objects.exists())

    def test_rechaza_sin_permiso_y_periodo_cerrado(self):
        r = self.jornada(date(2026, 8, 6))
        self.actor.rol = 'TRABAJADOR'
        with self.assertRaises(ValidationError): confirmar_feriado_trabajado(r, self.actor)
        self.actor.rol = 'CONTADORA'
        CierreAsistencia.objects.create(fecha_inicio=r.fecha, fecha_fin=r.fecha, total_jornadas=1)
        with self.assertRaises(ValidationError): confirmar_feriado_trabajado(r, self.actor)

    def test_boton_y_envio_conservan_detalle(self):
        r = self.jornada(date(2026, 8, 6))
        from django.template.loader import render_to_string
        html = render_to_string('asistencia/cuadro_excel.html', {
            'd': detalle_jornada(r), 'puede_aprobar': True, 'puede_gestionar': True,
        })
        self.assertIn('Confirmar feriado trabajado', html)
        respuesta = self.client.post(reverse('accion_jornada', args=[r.pk]), {
            'accion': 'confirmar_feriado_trabajado', 'persona_dni': self.ficha.dni,
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(f'detalle={r.pk}', respuesta.url)
        self.assertEqual(AjusteAsistencia.objects.get(resumen=r).minutos, 480)

    def test_restaurar_calculos_retira_adicional_y_conserva_marcaciones(self):
        r = self.jornada(date(2026, 8, 6), refrigerio=True)
        confirmar_feriado_trabajado(r, self.actor)
        originales = [m.pk for m in detalle_jornada(r)['marcas']]
        self.client.force_login(self.actor)
        respuesta = self.client.post(reverse('accion_jornada', args=[r.pk]), {'accion': 'restaurar_conceptos'})
        self.assertEqual(respuesta.status_code, 302)
        r.refresh_from_db()
        self.assertFalse(r.ajustes.filter(concepto='descanso_feriado').exists())
        d = detalle_jornada(r)
        self.assertEqual([m.pk for m in d['marcas']], originales)
        self.assertEqual(d['cuadro_excel']['totales']['feriado'], 'Sin registro')
        self.assertTrue(d['cuadro_excel']['puede_confirmar_feriado'])

    def test_solo_horas_sin_faltantes_ni_extras_y_feriado_exacto(self):
        from datetime import time, datetime
        from django.utils import timezone
        from asistencia.services.revision import valores_ajustados
        from asistencia.services.configuracion_horas import configurar_solo_horas
        r = self.jornada(date(2026, 8, 6), refrigerio=False)
        marcas = detalle_jornada(r)['marcas']
        ultima = marcas[-1]
        ultima.fecha_hora = timezone.make_aware(datetime.combine(r.fecha, time(12, 0, 20)))
        ultima.save()
        r.ultima_salida = time(12, 0, 20)
        r.save()
        configurar_solo_horas(self.ficha, True, self.actor)
        r.refresh_from_db()
        d = detalle_jornada(r)
        self.assertTrue(d['completa'])
        self.assertFalse(d['falta_refrigerio'])
        self.assertFalse(d['cuadro_excel']['totales']['es_deficit'])
        self.assertEqual(d['cuadro_excel']['totales']['he25'], '00:00:00')
        self.assertEqual(d['cuadro_excel']['totales']['he35'], '00:00:00')
        ajuste = confirmar_feriado_trabajado(r, self.actor)
        r.refresh_from_db()
        self.assertEqual(detalle_jornada(r)['cuadro_excel']['totales']['feriado'], d['cuadro_excel']['totales']['trabajo'])
        self.assertEqual(valores_ajustados(r)['horas_extras_25'], 0)

    def test_extras_desactivadas_conservan_trabajo_y_nocturnas(self):
        from asistencia.services.configuracion_horas import configurar_extras
        from asistencia.services.revision import valores_ajustados
        r = self.jornada(date(2026, 8, 6), refrigerio=True)
        trabajo = detalle_jornada(r)['cuadro_excel']['totales']['trabajo']
        configurar_extras(self.ficha, False, False, self.actor)
        r.refresh_from_db()
        d = detalle_jornada(r)
        self.assertEqual(d['cuadro_excel']['totales']['trabajo'], trabajo)
        self.assertEqual(d['cuadro_excel']['totales']['he25'], '00:00:00')
        self.assertEqual(d['cuadro_excel']['totales']['he35'], '00:00:00')
        self.assertEqual(valores_ajustados(r)['horas_extras_25'], 0)
        self.assertEqual(r.horas_extras_35, 0)
