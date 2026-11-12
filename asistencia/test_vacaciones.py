from datetime import date
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.urls import reverse
from core.models import Usuario
from asistencia.models import Trabajador, ResumenAsistenciaDiaria, PeriodoVacaciones, IncidenciaAsistencia
from asistencia.services.vacaciones import asignar_vacaciones, validar_vacaciones

class VacacionesTests(TestCase):
    def setUp(self):
        self.actor=Usuario.objects.create_user('vacaciones',email='vacaciones@example.invalid',dni='11223344',rol='CONTADORA')
        self.t=Trabajador.objects.create(nombre_completo='Trabajador Vacaciones',dni='22334455',area='VENTAS',sede='CHICLAYO')
        self.client.force_login(self.actor)

    def asignar(self):
        return asignar_vacaciones(self.t,date(2026,8,2),date(2026,8,4),self.actor)

    def test_asignar_y_validar_periodo_completo(self):
        p=self.asignar()
        self.assertEqual(ResumenAsistenciaDiaria.objects.count(),3)
        self.assertFalse(ResumenAsistenciaDiaria.objects.filter(verificado_contabilidad=True).exists())
        validar_vacaciones(p,self.actor)
        self.assertEqual(ResumenAsistenciaDiaria.objects.filter(verificado_contabilidad=True,estado='VACACIONES').count(),3)
        p.refresh_from_db();self.assertIsNotNone(p.aprobado_el)

    def test_conflicto_revierte_todo_el_rango(self):
        r=ResumenAsistenciaDiaria.objects.create(trabajador=self.t,fecha=date(2026,8,4),horas_trabajadas=2)
        with self.assertRaises(ValidationError):self.asignar()
        self.assertFalse(PeriodoVacaciones.objects.exists())
        self.assertEqual(ResumenAsistenciaDiaria.objects.count(),1)
        self.assertFalse(IncidenciaAsistencia.objects.exists())

    def test_validacion_con_conflicto_no_aprueba_parcialmente(self):
        p=self.asignar()
        r=ResumenAsistenciaDiaria.objects.get(fecha=date(2026,8,4))
        r.horas_trabajadas=2;r.save()
        with self.assertRaises(ValidationError):validar_vacaciones(p,self.actor)
        self.assertFalse(ResumenAsistenciaDiaria.objects.filter(verificado_contabilidad=True).exists())

    def test_ficha_y_navegacion_salta_solo_vacaciones_validadas(self):
        p=self.asignar()
        anterior=ResumenAsistenciaDiaria.objects.create(trabajador=self.t,fecha=date(2026,8,1))
        siguiente=ResumenAsistenciaDiaria.objects.create(trabajador=self.t,fecha=date(2026,8,5))
        params={'vista':'asistencia','desde':'2026-08-01','hasta':'2026-08-05','persona_dni':self.t.dni,'detalle':anterior.pk}
        response=self.client.get(reverse('dashboard'),params)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['detalle_jornada']['siguiente_fecha'],date(2026,8,2))
        validar_vacaciones(p,self.actor)
        response=self.client.get(reverse('dashboard'),params)
        self.assertEqual(response.context['detalle_jornada']['siguiente_fecha'],date(2026,8,5))
        response=self.client.get(reverse('dashboard'),{'vista':'personal','ficha':self.t.pk})
        self.assertContains(response,'Asignar vacaciones')

    def test_endpoint_valida_y_no_permite_periodo_ajeno(self):
        p=self.asignar();r=ResumenAsistenciaDiaria.objects.get(fecha=p.desde)
        response=self.client.post(reverse('accion_jornada',args=[r.pk]),{'accion':'validar_vacaciones','periodo_id':p.pk,'mantener_detalle':'si'})
        self.assertEqual(response.status_code,302)
        p.refresh_from_db();self.assertIsNotNone(p.aprobado_el)

    def test_solapamiento_y_permiso(self):
        self.asignar()
        with self.assertRaises(ValidationError):self.asignar()
        self.actor.rol='TRABAJADOR'
        with self.assertRaises(ValidationError):validar_vacaciones(PeriodoVacaciones.objects.get(),self.actor)

