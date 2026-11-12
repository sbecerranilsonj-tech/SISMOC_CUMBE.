from datetime import date, datetime, time
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from core.models import Usuario
from asistencia.models import (ReglaJornada, DiaEspecial, Trabajador, ResumenAsistenciaDiaria,
                               MarcacionBiometrica, IdentidadBiometrica, CierreAsistencia)
from asistencia.services.reglas_jornada import regla_para, calendario_especial, feriados_nacionales
from asistencia.services.cuadro_excel import base_jornada_segundos
from asistencia.services.revision import detalle_jornada
from asistencia.services.revision_trabajador import contexto_revision, validar_periodo


class ReglasJornadaTests(TestCase):
    def setUp(self):
        self.actor = Usuario.objects.create_user('reglas', email='reglas@example.invalid', dni='10000100', rol='CONTADORA')
        self.ficha = Trabajador.objects.create(nombre_completo='Diana Choquehuanca', dni='10000101', area='CONTABILIDAD', sede='CHICLAYO')
        self.identidad = IdentidadBiometrica.objects.create(trabajador=self.ficha, sede='CHICLAYO', codigo='123')
        self.fecha = date(2026, 8, 3)
        self.regla = ReglaJornada.objects.create(area='Contabilidad', desde=date(2026, 8, 1),
                                               minutos_diarios=510, minutos_sabado=270, minutos_refrigerio=60, motivo='Confirmado por empresa')
        self.client.force_login(self.actor)

    def jornada(self, fecha=None, marcas=True, refrigerio=False):
        fecha = fecha or self.fecha
        r = ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha, fecha=fecha, primera_entrada=time(9), ultima_salida=time(19))
        if marcas:
            eventos = [(9, 'ENTRADA'), (19, 'SALIDA')]
            if refrigerio:
                eventos = [(9, 'ENTRADA'), (13, 'SALIDA_REFRIGERIO'), (14, 'RETORNO_REFRIGERIO'), (19, 'SALIDA')]
            for hora, evento in eventos:
                MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad,
                    fecha_hora=timezone.make_aware(datetime.combine(fecha, time(hora))), tipo_evento=evento)
        return r

    def test_prioridad_vigencia_y_base_diaria(self):
        r = self.jornada()
        self.assertEqual(base_jornada_segundos(r), 510 * 60)
        ReglaJornada.objects.create(area='CONTABILIDAD', desde=date(2026, 8, 5), minutos_diarios=570, motivo='Rotación')
        self.assertEqual(regla_para(self.ficha, date(2026, 8, 5)).minutos_diarios, 570)
        self.assertEqual(regla_para(self.ficha, self.fecha).minutos_diarios, 510)
        individual = ReglaJornada.objects.create(trabajador=self.ficha, desde=self.fecha, hasta=self.fecha, minutos_diarios=480, motivo='Excepción')
        self.assertEqual(regla_para(self.ficha, self.fecha), individual)
        r.conceptos_editados = {'jornada_base': 7 * 3600}
        self.assertEqual(base_jornada_segundos(r), 7 * 3600)

    def test_sabado_y_domingo_no_se_confunden(self):
        sabado = self.jornada(date(2026, 8, 8), marcas=False)
        self.assertEqual(base_jornada_segundos(sabado), 270 * 60)
        domingo = self.jornada(date(2026, 8, 9), marcas=False)
        self.assertEqual(base_jornada_segundos(domingo), 510 * 60)

    def test_feriados_y_dia_empresa_no_inventan_ausencia(self):
        fechas = feriados_nacionales(2026)
        self.assertEqual(len(fechas), 16)
        self.assertEqual(fechas[date(2026, 4, 2)], 'Jueves Santo')
        self.assertNotIn(date(2026, 1, 2), fechas)
        DiaEspecial.objects.create(fecha=self.fecha, nombre='Aniversario')
        self.assertEqual(calendario_especial(self.fecha, self.fecha)[self.fecha], 'Aniversario')
        r = self.jornada(marcas=False)
        self.assertFalse(detalle_jornada(r)['ausencia_justificada'])

    def test_refrigerio_faltante_bloquea_y_confirmacion_recalcula(self):
        r = self.jornada()
        d = detalle_jornada(r)
        self.assertTrue(d['falta_refrigerio'])
        self.assertTrue(d['bloqueos'])
        self.assertEqual(d['cuadro_excel']['totales']['trabajo'], 'Por revisar')
        respuesta = self.client.post(reverse('accion_jornada', args=[r.pk]), {'accion': 'confirmar_refrigerio', 'motivo': 'Confirmó descanso de una hora'})
        self.assertEqual(respuesta.status_code, 302)
        r.refresh_from_db()
        self.assertEqual(r.conceptos_editados['refrigerio_confirmado'], 3600)
        self.assertEqual(r.horas_trabajadas, Decimal('9.00'))
        self.assertEqual(r.horas_extras_25, Decimal('0.50'))
        self.assertEqual(MarcacionBiometrica.objects.count(), 2)
        d = detalle_jornada(r)
        self.assertEqual(d['trabajo_reconstruido'], '09:00:00')
        self.assertEqual(d['refrigerio'], '01:00:00')
        self.assertFalse(d['falta_refrigerio'])
        self.assertFalse(d['bloqueos'])

    def test_refrigerio_marcado_no_se_descuenta_dos_veces(self):
        r = self.jornada(refrigerio=True)
        validar_periodo([r], {}, {}, None, 'Validado', self.actor)
        r.refresh_from_db()
        self.assertEqual(r.horas_trabajadas, Decimal('9.00'))
        self.assertFalse(detalle_jornada(r)['falta_refrigerio'])
        r.conceptos_editados = {'refrigerio_confirmado': 3600}
        self.assertTrue(any('Retire el descuento' in b for b in detalle_jornada(r)['bloqueos']))

    def test_socia_sin_marcas_no_genera_horas_ni_falta(self):
        ReglaJornada.objects.create(trabajador=self.ficha, desde=self.fecha, exento_marcacion=True, motivo='Socia')
        r = self.jornada(marcas=False)
        d = detalle_jornada(r)
        self.assertTrue(d['exenta_marcacion'])
        self.assertFalse(d['bloqueos'])
        r.refresh_from_db()
        self.assertEqual(r.horas_trabajadas, 0)
        self.assertNotEqual(r.estado, 'FALTA')

    def test_socia_con_marcas_conserva_trabajo(self):
        ReglaJornada.objects.create(trabajador=self.ficha, desde=self.fecha, exento_marcacion=True, motivo='Socia')
        r = self.jornada(refrigerio=True)
        self.assertFalse(detalle_jornada(r)['exenta_marcacion'])
        self.assertEqual(MarcacionBiometrica.objects.count(), 4)

    def datos_regla(self):
        return {'regla-area': 'CONTABILIDAD', 'regla-desde': '2026-08-01', 'regla-hasta': '2026-08-31',
                'regla-minutos_diarios': 570, 'regla-minutos_sabado': 270, 'regla-minutos_refrigerio': 60,
                'regla-motivo': 'Horario confirmado'}

    def test_configuracion_protege_periodos_cerrados(self):
        CierreAsistencia.objects.create(fecha_inicio=self.fecha, fecha_fin=self.fecha, cerrado_por=self.actor, total_jornadas=0)
        cantidad = ReglaJornada.objects.count()
        res = self.client.post(reverse('reglas_jornada'), self.datos_regla())
        self.assertContains(res, 'periodo cerrado')
        self.assertEqual(ReglaJornada.objects.count(), cantidad)

    def test_regla_nueva_reabre_aprobacion_y_deja_historial(self):
        r = self.jornada(refrigerio=True)
        r.verificado_contabilidad = True
        r.save(update_fields=['verificado_contabilidad'])
        res = self.client.post(reverse('reglas_jornada'), self.datos_regla())
        self.assertEqual(res.status_code, 302)
        r.refresh_from_db()
        self.assertFalse(r.verificado_contabilidad)
        self.assertTrue(r.historial_revision.exists())

    def test_pagina_y_calendario_muestran_reglas_y_colores(self):
        self.assertContains(self.client.get(reverse('reglas_jornada')), 'Guardar día especial')
        r = self.jornada(refrigerio=True)
        ctx = contexto_revision([r], date(2026, 8, 3), date(2026, 8, 8))
        self.assertEqual(ctx['calendario'][3]['especial'], 'Batalla de Junín')
        self.assertTrue(ctx['calendario'][-1]['es_sabado'])
        from django.template.loader import render_to_string
        html = render_to_string('asistencia/revision_trabajador.html', {'revision_trabajador': ctx})
        self.assertIn('dia-sabado', html)
        self.assertIn('dia-especial', html)

    def test_usuario_sin_permiso_no_configura(self):
        lector = Usuario.objects.create_user('lector', email='lector@example.invalid', dni='10000102', rol='CONDUCTOR')
        self.client.force_login(lector)
        self.assertEqual(self.client.post(reverse('reglas_jornada'), self.datos_regla()).status_code, 403)
