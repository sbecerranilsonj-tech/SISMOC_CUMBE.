from datetime import date
from asistencia.test_reglas_jornada import ReglasJornadaTests
from asistencia.services.cuadro_excel import base_jornada_segundos
from asistencia.services.revision import detalle_jornada
from asistencia.services.revision_trabajador import validar_periodo


from django.test import TestCase


class BaseContableAutomaticaTests(TestCase):
    setUp = ReglasJornadaTests.setUp
    jornada = ReglasJornadaTests.jornada

    def test_dos_marcas_base_nueve_treinta_sin_doble_descuento(self):
        r = self.jornada()
        self.assertEqual(base_jornada_segundos(r), 570 * 60)
        d = detalle_jornada(r)
        self.assertFalse(d['falta_refrigerio'])
        self.assertEqual(d['cuadro_excel']['totales']['saldo'], '00:30:00')
        validar_periodo([r], {}, {}, None, 'Validación', self.actor)
        r.refresh_from_db()
        self.assertEqual(str(r.horas_trabajadas), '10.00')
        self.assertEqual(str(r.horas_extras_25), '0.50')
        self.assertFalse(r.verificado_contabilidad)

    def test_cuatro_marcas_base_ocho_treinta(self):
        r = self.jornada(refrigerio=True)
        self.assertEqual(base_jornada_segundos(r), 510 * 60)
        self.assertEqual(detalle_jornada(r)['cuadro_excel']['totales']['saldo'], '00:30:00')

    def test_sabado_y_prioridad_manual(self):
        r = self.jornada(date(2026, 8, 8))
        self.assertEqual(base_jornada_segundos(r), 270 * 60)
        r.conceptos_editados = {'jornada_base': 18000}
        self.assertEqual(base_jornada_segundos(r), 18000)

    def test_asistente_contable_y_otras_areas(self):
        self.ficha.area = 'ASISTENTE CONTABLE'
        r = self.jornada()
        self.assertEqual(base_jornada_segundos(r), 570 * 60)
        self.ficha.area = 'BOLETERIA'
        r._regla_jornada = None
        self.assertEqual(base_jornada_segundos(r), 525 * 60)

    def test_cambio_base_recalcula_minimo_dos_horas(self):
        from asistencia.services.edicion_conceptos import guardar_conceptos
        from asistencia.services.cuadro_excel import formato_tiempo
        r = self.jornada(refrigerio=True)
        r.conceptos_editados = {'jornada_base': 28800}
        r.save(update_fields=['conceptos_editados'])
        guardar_conceptos(r, {'jornada_base':'08:30:00','horas_extras_25':'01:00:00','horas_extras_35':'00:00:00','horas_nocturnas':'00:00:00'}, self.actor)
        self.assertEqual(r.conceptos_editados['horas_extras_25'],1800)
        self.assertEqual(formato_tiempo(min(4644,7200)), '01:17:24')

    def test_repetida_42_segundos_requiere_revision_y_es_reversible(self):
        from datetime import datetime, time
        from django.utils import timezone
        from asistencia.models import MarcacionBiometrica
        from asistencia.services.duplicadas import revisar_duplicada
        from asistencia.services.revision import revisar
        from django.core.exceptions import ValidationError
        r = self.jornada()
        r.ultima_salida = time(19,1)
        r.save(update_fields=['ultima_salida'])
        repetida = MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad,fecha_hora=timezone.make_aware(datetime.combine(r.fecha,time(19,0,42))),tipo_evento='SIN_CLASIFICAR')
        d = detalle_jornada(r)
        self.assertIsNone(base_jornada_segundos(r))
        self.assertFalse(d['completa'])
        self.assertEqual(len(d['filas_duplicadas']), 2)
        self.assertEqual(d['cuadro_excel']['totales']['base'], 'Por revisar')
        with self.assertRaises(ValidationError):
            revisar(r,self.actor,'APROBADO')
        revisar_duplicada(r,self.actor,repetida.pk)
        self.assertEqual(base_jornada_segundos(r),570*60)
        self.assertFalse(r.verificado_contabilidad)
        revisar_duplicada(r,self.actor,repetida.pk,restaurar=True)
        self.assertIsNone(base_jornada_segundos(r))
        self.assertEqual(MarcacionBiometrica.objects.filter(identidad_biometrica=self.identidad).count(),3)

    def test_clasificar_y_excluir_dos_marcas_sabado(self):
        from datetime import datetime, time
        from django.utils import timezone
        from asistencia.models import MarcacionBiometrica
        from asistencia.services.duplicadas import revisar_duplicada
        r = self.jornada(date(2026,8,22),marcas=False)
        horarios = [time(9,26,51),time(9,29,14),time(13,41,55),time(13,47,41)]
        r.primera_entrada, r.ultima_salida = horarios[0], horarios[-1]
        r.save()
        marcas = [MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad,fecha_hora=timezone.make_aware(datetime.combine(r.fecha,h)),tipo_evento='SIN_CLASIFICAR') for h in horarios]
        from django.db import transaction
        with transaction.atomic():
            validar_periodo([r],dict(zip([m.pk for m in marcas],['ENTRADA','EXCLUIR_DUPLICADA','EXCLUIR_DUPLICADA','SALIDA'])),{m.pk:'SIN_CLASIFICAR' for m in marcas},None,'Revisión de duplicadas',self.actor)
        d = detalle_jornada(r)
        self.assertTrue(d['completa'])
        self.assertEqual(d['cuadro_excel']['totales']['trabajo'],'04:20:50')
        self.assertEqual(d['cuadro_excel']['totales']['saldo'],'−00:09:10')
        self.assertEqual(len([f for f in d['cuadro_excel']['filas'] if f['excluida_duplicada']]),2)
        self.assertFalse(r.verificado_contabilidad)
        revisar_duplicada(r,self.actor,marcas[1].pk,restaurar=True)
        self.assertFalse(detalle_jornada(r)['completa'])
        self.assertEqual(MarcacionBiometrica.objects.filter(identidad_biometrica=self.identidad).count(),4)

    def test_formula_excel_conserva_faltante_negativo(self):
        from datetime import time
        from django.db import transaction
        from asistencia.services.revision import valores_ajustados
        from asistencia.services.edicion_conceptos import guardar_conceptos
        r = self.jornada()
        r.conceptos_editados = {'jornada_base': 10*3600+556}
        r.save()
        with transaction.atomic():
            validar_periodo([r],{}, {},None,'Fórmula Excel',self.actor)
        d=detalle_jornada(r)
        self.assertEqual(d['cuadro_excel']['totales']['he25'],'−00:09:16')
        self.assertEqual(d['cuadro_excel']['totales']['he35'],'00:00:00')
        self.assertLess(valores_ajustados(r)['horas_extras_25'],0)
        self.assertNotIn('Los conceptos no pueden quedar con total negativo.',d['bloqueos'])
        guardar_conceptos(r,{'jornada_base':'10:09:16','horas_extras_25':'−00:09:16','horas_extras_35':'00:00:00','horas_nocturnas':'00:00:00'},self.actor)
        self.assertEqual(r.conceptos_editados['horas_extras_25'],-556)

    def test_tesoreria_comparte_regla_contable(self):
        for area in ['TESORERA','TESORERO','TESORERÍA']:
            self.ficha.area=area
            r=self.jornada()
            self.assertEqual(base_jornada_segundos(r),570*60)
            r.delete()
            from asistencia.models import MarcacionBiometrica
            MarcacionBiometrica.objects.filter(identidad_biometrica=self.identidad).delete()

    def test_contadora_general_aplica_base_contable(self):
        self.ficha.area='CONTADORA GENERAL'
        r=self.jornada()
        self.assertEqual(base_jornada_segundos(r),570*60)
        from asistencia.models import MarcacionBiometrica
        MarcacionBiometrica.objects.filter(identidad_biometrica=self.identidad).delete()
        r.delete()
        r=self.jornada(refrigerio=True)
        self.assertEqual(base_jornada_segundos(r),510*60)

    def test_control_contable_no_exige_horario_fijo(self):
        r=self.jornada()
        from django.db import transaction
        with transaction.atomic():
            validar_periodo([r],{}, {},None,'Validación',self.actor)
        d=detalle_jornada(r)
        self.assertTrue(d['control_por_jornada'])
        self.assertEqual(d['estado_asistencia_visible'],'Control por jornada · Sin horario fijo asignado')
        self.assertFalse(d['tardanza_confirmada'])
        self.assertFalse(d['bloqueos'])

    def test_regla_general_areas_y_dias_con_dos_y_cuatro_marcas(self):
        from asistencia.models import MarcacionBiometrica
        for area in ['AUXILIAR DE VENTAS', 'BOLETERÍA', 'VIGILANTE', 'ALMACÉN', '']:
            for fecha in [date(2026,8,3),date(2026,8,8),date(2026,8,9)]:
                for refrigerio,base in [(False,525),(True,480)]:
                    self.ficha.area=area
                    r=self.jornada(fecha,refrigerio=refrigerio)
                    self.assertEqual(base_jornada_segundos(r),base*60,(area,fecha,refrigerio))
                    d=detalle_jornada(r)
                    self.assertFalse(d['falta_refrigerio'])
                    self.assertEqual(d['cuadro_excel']['totales']['saldo'],'01:00:00' if refrigerio else '01:15:00')
                    MarcacionBiometrica.objects.filter(identidad_biometrica=self.identidad).delete()
                    r.delete()

    def test_regla_general_ignora_excluidas_y_conserva_base_manual(self):
        from datetime import datetime,time
        from django.utils import timezone
        from asistencia.models import MarcacionBiometrica
        self.ficha.area='AUXILIAR DE VENTAS'
        r=self.jornada()
        MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad,fecha_hora=timezone.make_aware(datetime.combine(r.fecha,time(18))),es_valida=False)
        self.assertEqual(base_jornada_segundos(r),525*60)
        r.conceptos_editados={'jornada_base':7*3600}
        self.assertEqual(base_jornada_segundos(r),7*3600)
