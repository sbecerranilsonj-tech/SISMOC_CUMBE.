from datetime import date
from django.core.exceptions import ValidationError
from django.test import TestCase
from asistencia import test_reglas_jornada as fixtures
from asistencia.models import DescansoProgramado, ResumenAsistenciaDiaria, AjusteAsistencia, CierreAsistencia
from asistencia.services.revision import detalle_jornada, revisar
from asistencia.services.reglas_jornada import descanso_previsto
from asistencia.services.descanso_trabajado import confirmar_descanso_trabajado


class DescansoTrabajadoTests(TestCase):
    setUp = fixtures.ReglasJornadaTests.setUp
    jornada = fixtures.ReglasJornadaTests.jornada

    def preparar(self):
        r = self.jornada(date(2026,8,8))
        DescansoProgramado.objects.create(trabajador=self.ficha, desde=date(2026,8,1), hasta=date(2026,8,31), dias=[5], responsable=self.actor)
        return r

    def test_sabado_no_es_descanso_automaticamente(self):
        r = self.jornada(date(2026,8,8))
        self.assertFalse(detalle_jornada(r)['trabajo_en_descanso'])

    def test_bloquea_aprobacion_hasta_confirmar_sin_generar_horas(self):
        r = self.preparar()
        d = detalle_jornada(r)
        self.assertTrue(d['trabajo_en_descanso'])
        self.assertFalse(d['descanso_confirmado'])
        with self.assertRaises(ValidationError): revisar(r, self.actor, 'APROBADO')
        confirmar_descanso_trabajado(r, 'DESCANSO_TRABAJADO', '', self.actor)
        r.refresh_from_db()
        self.assertTrue(detalle_jornada(r)['descanso_confirmado'])
        self.assertFalse(r.verificado_contabilidad)
        self.assertFalse(AjusteAsistencia.objects.exists())
        self.assertEqual(detalle_jornada(r)['cuadro_excel']['totales']['trabajo'], d['cuadro_excel']['totales']['trabajo'])

    def test_cambio_requiere_fecha_y_programa_sin_crear_asistencia(self):
        r = self.preparar()
        with self.assertRaises(ValidationError): confirmar_descanso_trabajado(r, 'CAMBIO_DESCANSO', '', self.actor)
        confirmar_descanso_trabajado(r, 'CAMBIO_DESCANSO', '2026-08-10', self.actor)
        self.assertTrue(descanso_previsto(ResumenAsistenciaDiaria(trabajador=self.ficha, fecha=date(2026,8,10))))
        self.assertFalse(ResumenAsistenciaDiaria.objects.filter(fecha=date(2026,8,10)).exists())
        confirmar_descanso_trabajado(r, 'CAMBIO_DESCANSO', '2026-08-10', self.actor)
        self.assertEqual(DescansoProgramado.objects.count(), 2)
        confirmar_descanso_trabajado(r, 'DESCANSO_TRABAJADO', '', self.actor)
        self.assertFalse(descanso_previsto(ResumenAsistenciaDiaria(trabajador=self.ficha, fecha=date(2026,8,10))))

    def test_destino_con_marcas_o_cierre_no_permitido(self):
        r = self.preparar()
        self.jornada(date(2026,8,10))
        with self.assertRaises(ValidationError): confirmar_descanso_trabajado(r, 'CAMBIO_DESCANSO', '2026-08-10', self.actor)
        CierreAsistencia.objects.create(fecha_inicio=date(2026,8,11), fecha_fin=date(2026,8,11), total_jornadas=0)
        with self.assertRaises(ValidationError): confirmar_descanso_trabajado(r, 'CAMBIO_DESCANSO', '2026-08-11', self.actor)
        self.assertEqual(DescansoProgramado.objects.count(), 1)

    def test_sin_permiso_no_confirma(self):
        r = self.preparar()
        self.actor.rol = 'TRABAJADOR'
        with self.assertRaises(ValidationError): confirmar_descanso_trabajado(r, 'DESCANSO_TRABAJADO', '', self.actor)

    def test_detalle_y_envio_conservan_contexto(self):
        from django.urls import reverse
        r = self.preparar()
        respuesta = self.client.get(reverse('dashboard'), {'vista':'asistencia', 'desde':'2026-08-01', 'hasta':'2026-08-31', 'persona_dni':self.ficha.dni, 'detalle':r.pk})
        self.assertContains(respuesta, 'Marcaciones en descanso programado')
        self.assertContains(respuesta, 'name="fecha_descanso"')
        respuesta = self.client.post(reverse('accion_jornada', args=[r.pk]), {'accion':'confirmar_descanso_trabajado', 'tipo_descanso':'CAMBIO_DESCANSO', 'fecha_descanso':'2026-08-10', 'persona_dni':self.ficha.dni, 'desde':'2026-08-01', 'hasta':'2026-08-31'})
        self.assertIn(f'detalle={r.pk}', respuesta.url)
        r.refresh_from_db()
        self.assertEqual(r.conceptos_editados['situacion_descanso']['fecha_destino'], '2026-08-10')
