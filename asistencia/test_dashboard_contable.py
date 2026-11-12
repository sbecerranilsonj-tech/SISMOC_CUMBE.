from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from asistencia import test_aprobacion_masiva as fixtures
from asistencia.models import AjusteAsistencia, IncidenciaAsistencia, ResumenAsistenciaDiaria, MarcacionBiometrica
from asistencia.services.dashboard_contable import resumen_dashboard
from core.models import Usuario


class DashboardContableTests(TestCase):
    def setUp(self):
        fixtures.AprobacionMasivaTests.setUp(self)

    def pantalla(self, **params):
        return self.client.get(reverse('dashboard'), {'vista': 'dashboard', 'desde': str(self.desde), 'hasta': str(self.hasta), **params})

    def test_trabajadores_no_se_confunden_con_cuentas_y_listas_no_aprueban(self):
        r = self.pantalla()
        dc = r.context['dashboard_contable']
        self.assertEqual(dc['trabajadores'], 1)
        self.assertEqual(dc['jornadas'], 2)
        self.assertEqual(dc['listas'], 2)
        self.assertEqual(dc['por_validar'], 0)
        self.assertEqual(dc['aprobadas'], 0)
        self.assertIn('persona_dni=' + self.ficha.dni, dc['prioridades'][0]['url'])
        self.assertFalse(ResumenAsistenciaDiaria.objects.filter(verificado_contabilidad=True).exists())

    def test_extras_separadas_y_ajustes_solo_aprobados(self):
        a, b = self.jornadas
        a.verificado_contabilidad = True
        a.horas_extras_25 = Decimal('1.25')
        a.save()
        b.horas_extras_25 = Decimal('2.00'); b.save()
        AjusteAsistencia.objects.create(resumen=a, concepto='horas_extras_25', minutos=30, motivo='Prueba aprobada', creado_por=self.contadora, aprobado_por=self.contadora, aprobado_el=timezone.now())
        AjusteAsistencia.objects.create(resumen=b, concepto='horas_extras_25', minutos=60, motivo='Prueba pendiente', creado_por=self.contadora)
        a.refresh_from_db()
        a.verificado_contabilidad = True
        a.save(update_fields=['verificado_contabilidad'])
        dc = self.pantalla().context['dashboard_contable']
        self.assertEqual(dc['horas']['aprobadas']['he25'], Decimal('1.75'))
        self.assertEqual(dc['horas']['pendientes']['he25'], Decimal('2.00'))
        self.assertEqual(dc['por_validar'], 1)

    def test_prioriza_incompletas_y_no_ofrece_aprobar_situaciones(self):
        MarcacionBiometrica.objects.filter(fecha_hora__date=self.desde, tipo_evento='SALIDA').update(tipo_evento='SIN_CLASIFICAR')
        r = ResumenAsistenciaDiaria.objects.create(trabajador=self.ficha, fecha=self.hasta + timedelta(days=1), estado='DIA_LIBRE')
        IncidenciaAsistencia.objects.create(resumen=r, tipo='DESCANSO_SEMANAL', motivo='Descanso', creado_por=self.contadora, aprobado_por=self.contadora, aprobado_el=timezone.now())
        dc = self.pantalla(hasta=str(r.fecha)).context['dashboard_contable']
        self.assertEqual(dc['por_validar'], 1)
        self.assertEqual(dc['listas'], 1)
        self.assertEqual(dc['situaciones'], 1)
        self.assertEqual(dc['prioridades'][0]['accion'], 'Revisar')

    def test_cierres_vacios_parciales_y_contiguos(self):
        f = {'desde': str(self.desde), 'hasta': str(self.hasta)}
        cierre = lambda a, b: SimpleNamespace(fecha_inicio=a, fecha_fin=b)
        self.assertEqual(resumen_dashboard([], f, [])['cierre'], 'Abierto')
        self.assertEqual(resumen_dashboard([], f, [cierre(self.desde, self.desde)])['cierre'], 'Cierre parcial')
        dc = resumen_dashboard([], f, [cierre(self.desde, self.desde), cierre(self.hasta, self.hasta)])
        self.assertEqual(dc['cierre'], 'Cerrado')
        self.assertEqual(dc['trabajadores'], 0)

    def test_filtros_y_privacidad_del_panel_contable(self):
        vacio = self.pantalla(desde='2026-09-01', hasta='2026-09-30')
        self.assertEqual(vacio.context['dashboard_contable']['jornadas'], 0)
        self.assertContains(vacio, 'No hay jornadas registradas en este periodo')
        empleado = Usuario.objects.create_user('solo_personal', email='personal@example.invalid', dni='33333333', rol='BOLETERIA')
        self.client.force_login(empleado)
        res = self.pantalla()
        self.assertIsNone(res.context['dashboard_contable'])
        self.assertNotContains(res, 'Pendientes prioritarios')
