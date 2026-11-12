from datetime import date
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import Usuario
from asistencia.models import Trabajador, ResumenAsistenciaDiaria, IncidenciaAsistencia, CierreAsistencia
from asistencia.services.revision import revisar


class SeleccionSituacionTests(TestCase):
    def setUp(self):
        self.actor=Usuario.objects.create_user('situacion_confirmada',email='situacion@example.invalid',dni='11111111',rol='CONTADORA')
        self.persona=Trabajador.objects.create(nombre_completo='Persona Prueba',dni='22222222',area='Boletería',sede='CAJAMARCA')
        self.r=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=date(2026,8,11),estado='DIA_LIBRE')
        self.i=IncidenciaAsistencia.objects.create(resumen=self.r,tipo='DESCANSO_SEMANAL',motivo='Descanso registrado',creado_por=self.actor,aprobado_por=self.actor,aprobado_el=timezone.now())
        self.client.force_login(self.actor)
        self.url=reverse('accion_jornada',args=[self.r.pk])

    def post(self,**datos):
        return self.client.post(self.url,{'accion':'aprobar_dia_situacion','solo_situacion':'si',**datos})

    def test_no_aprueba_sin_seleccion_ni_por_accion_anterior(self):
        for datos in [{},{'tipo':'NO_VALIDO'},{'accion':'APROBADO'}]:
            self.post(**datos);self.r.refresh_from_db();self.i.refresh_from_db()
            self.assertFalse(self.r.verificado_contabilidad)
            self.assertEqual(self.i.motivo,'Descanso registrado')
        with self.assertRaises(ValidationError): revisar(self.r,self.actor,'APROBADO')

    def test_seleccion_explicita_aprueba_y_registra_historial(self):
        self.post(tipo='DESCANSO_SEMANAL');self.r.refresh_from_db()
        self.assertTrue(self.r.verificado_contabilidad)
        self.assertTrue(self.r.historial_revision.filter(accion='Situación confirmada para aprobación',detalle__contains='Descanso semanal').exists())

    def test_cambiar_situacion_guarda_eleccion_y_preserva_motivo_anterior_en_historial(self):
        self.post(tipo='VACACIONES');self.r.refresh_from_db();self.i.refresh_from_db()
        self.assertEqual(self.r.estado,'VACACIONES')
        self.assertEqual(self.i.tipo,'VACACIONES')
        self.assertEqual(self.i.motivo,'Vacaciones')
        self.assertTrue(self.r.verificado_contabilidad)
        self.assertTrue(self.r.historial_revision.filter(detalle__contains='Descanso registrado').exists())

    def test_permiso_exige_justificacion_sin_cambios_parciales(self):
        self.post(tipo='PERMISO');self.r.refresh_from_db();self.i.refresh_from_db()
        self.assertFalse(self.r.verificado_contabilidad)
        self.assertEqual(self.i.tipo,'DESCANSO_SEMANAL')
        self.post(tipo='PERMISO',motivo='Trámite personal autorizado');self.r.refresh_from_db();self.i.refresh_from_db()
        self.assertTrue(self.r.verificado_contabilidad)
        self.assertEqual(self.i.motivo,'Trámite personal autorizado')
        respuesta = self.client.get(reverse('dashboard'), {'vista':'asistencia',
            'desde':str(self.r.fecha),'hasta':str(self.r.fecha),'persona_dni':self.persona.dni})
        self.assertContains(respuesta, 'Ver justificación')
        self.assertContains(respuesta, 'Trámite personal autorizado')
        self.assertContains(respuesta, 'Aprobado el')

    def test_otras_situaciones_no_exigen_justificacion(self):
        self.post(tipo='FERIADO_NO_LABORADO');self.r.refresh_from_db()
        self.assertTrue(self.r.verificado_contabilidad)
        self.assertEqual(self.r.estado,'FERIADO')

    def test_no_laboro_aprueba_dia_como_no_laborado(self):
        self.post(tipo='NO_LABORO');self.r.refresh_from_db();self.i.refresh_from_db()
        self.assertTrue(self.r.verificado_contabilidad)
        self.assertEqual(self.r.estado,'NO_LABORO')
        self.assertEqual(self.i.tipo,'NO_LABORO')
        self.assertEqual(self.i.motivo,'No laboró')
        self.assertEqual(self.i.get_tipo_display(),'No laboró')

    def test_cierre_impide_cambio_y_aprobacion(self):
        CierreAsistencia.objects.create(fecha_inicio=self.r.fecha,fecha_fin=self.r.fecha,total_jornadas=1)
        self.post(tipo='VACACIONES');self.r.refresh_from_db();self.i.refresh_from_db()
        self.assertFalse(self.r.verificado_contabilidad)
        self.assertEqual(self.i.tipo,'DESCANSO_SEMANAL')

    def test_no_permite_aprobacion_al_administrador(self):
        self.actor.rol='ADMINISTRADOR';self.actor.save()
        self.post(tipo='VACACIONES');self.r.refresh_from_db()
        self.assertFalse(self.r.verificado_contabilidad)

    def test_situacion_pendiente_se_puede_confirmar_desde_la_fila(self):
        self.i.aprobado_el=None;self.i.aprobado_por=None;self.i.save()
        self.post(tipo='DESCANSO_SEMANAL');self.r.refresh_from_db();self.i.refresh_from_db()
        self.assertTrue(self.r.verificado_contabilidad)
        self.assertIsNotNone(self.i.aprobado_el)

    def test_ui_no_preselecciona_un_motivo(self):
        res=self.client.get(reverse('dashboard'),{'vista':'asistencia','desde':str(self.r.fecha),'hasta':str(self.r.fecha),'persona_dni':self.persona.dni})
        self.assertContains(res,'Seleccione antes de aprobar')
        self.assertContains(res,'value="aprobar_dia_situacion"')
        self.assertContains(res,'Seleccionar situación')

    def test_confirmar_situacion_desde_detalle_vacio_conserva_navegacion(self):
        self.i.delete()
        self.r.estado='POR_REVISAR';self.r.save()
        params={'vista':'asistencia','desde':str(self.r.fecha),'hasta':str(self.r.fecha),'detalle':self.r.pk,'persona_dni':self.persona.dni}
        response=self.client.get(reverse('dashboard'),params)
        self.assertContains(response,'Registrar situación')
        response=self.post(tipo='DESCANSO_SEMANAL',mantener_detalle='si',persona_dni=self.persona.dni,desde=str(self.r.fecha),hasta=str(self.r.fecha))
        self.assertIn('detalle='+str(self.r.pk),response.url)
        self.r.refresh_from_db()
        self.assertTrue(self.r.verificado_contabilidad)
        self.assertEqual(self.r.incidencias.get().tipo,'DESCANSO_SEMANAL')
        self.assertContains(self.client.get(response.url),'Descanso semanal')

    def test_permiso_en_dia_vacio_exige_justificacion(self):
        self.i.delete()
        self.post(tipo='PERMISO')
        self.r.refresh_from_db()
        self.assertFalse(self.r.verificado_contabilidad)
        self.assertFalse(self.r.incidencias.exists())
        self.post(tipo='PERMISO',motivo='Permiso confirmado por supervisión')
        self.r.refresh_from_db()
        self.assertTrue(self.r.verificado_contabilidad)

    def test_cumpleanos_se_aprueba_sin_motivo_y_se_identifica_visualmente(self):
        self.post(tipo='CUMPLEANOS')
        self.r.refresh_from_db();self.i.refresh_from_db()
        self.assertTrue(self.r.verificado_contabilidad)
        self.assertEqual(self.i.tipo,'CUMPLEANOS')
        self.assertEqual(self.i.motivo,'Cumpleaños')
        self.assertEqual(self.r.horas_trabajadas,0)
        respuesta=self.client.get(reverse('dashboard'),{'vista':'asistencia','desde':str(self.r.fecha),'hasta':str(self.r.fecha),'persona_dni':self.persona.dni,'detalle':self.r.pk})
        self.assertContains(respuesta,'birthday-label')
        self.assertContains(respuesta,'Cumpleaños')
