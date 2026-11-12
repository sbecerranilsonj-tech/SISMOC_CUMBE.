from datetime import date, datetime, time, timedelta
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from core.models import Usuario
from asistencia.models import Trabajador, IdentidadBiometrica, MarcacionBiometrica, ResumenAsistenciaDiaria, TurnoHorario, CorreccionEvento, CierreAsistencia
from asistencia.services.transferencia import pasar_a_asistencia
from asistencia.services.revision import detalle_jornada, revisar
from asistencia.services.horarios import programar_horarios


class PropuestaEventosTests(TestCase):
    def setUp(self):
        self.actor=Usuario.objects.create_user('propuestas',email='propuestas@example.invalid',dni='10101010',rol='CONTADORA')
        self.persona=Trabajador.objects.create(nombre_completo='Trabajador Propuestas',dni='20202020',area='Boletería',sede='CAJAMARCA')
        self.identidad=IdentidadBiometrica.objects.create(trabajador=self.persona,sede='CAJAMARCA',equipo='1',codigo='42')
        self.dia=date(2026,8,1)
        self.turno=TurnoHorario.objects.create(nombre='Mañana',hora_entrada=time(8),hora_salida=time(17))
        self.client.force_login(self.actor)

    def marca(self,hora,fecha=None,**kwargs):
        return MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad,fecha_hora=timezone.make_aware(datetime.combine(fecha or self.dia,hora)),tipo_evento='SIN_CLASIFICAR',**kwargs)

    def enviar(self):
        pasar_a_asistencia([self.persona.pk],self.dia,self.dia,self.actor)
        return ResumenAsistenciaDiaria.objects.get(fecha=self.dia)

    def cuatro(self):
        return [self.marca(h) for h in [time(8),time(12),time(13),time(17)]]

    def test_cuatro_se_proponen_sin_guardar_ni_validar_ni_aprobar(self):
        marcas=self.cuatro()
        r=self.enviar()
        d=detalle_jornada(r)
        self.assertEqual(list(d['propuestas_eventos'].values()),['ENTRADA','SALIDA_REFRIGERIO','RETORNO_REFRIGERIO','SALIDA'])
        self.assertFalse(d['completa'])
        self.assertEqual(r.horas_trabajadas,0)
        self.assertFalse(r.verificado_contabilidad)
        self.assertFalse(CorreccionEvento.objects.exists())
        self.assertTrue(all(m.tipo_evento=='SIN_CLASIFICAR' for m in MarcacionBiometrica.objects.all()))
        with self.assertRaises(ValidationError): revisar(r,self.actor,'APROBADO')
        filas=d['cuadro_excel']['filas']
        self.assertEqual(filas[0]['evento_codigo'],'SIN_CLASIFICAR')
        self.assertEqual(filas[0]['evento_seleccionado'],'ENTRADA')

    def test_confirmacion_guarda_correcciones_recalcula_y_aprobacion_va_aparte(self):
        self.cuatro();r=self.enviar()
        programar_horarios(self.persona,self.dia,self.dia,[5],self.turno,'Confirmado',self.actor)
        data={'accion':'corregir_eventos','desde':str(self.dia),'hasta':str(self.dia),'vista':'asistencia'}
        for pk,evento in detalle_jornada(r)['propuestas_eventos'].items():
            data[f'evento_{pk}']=evento;data[f'original_{pk}']='SIN_CLASIFICAR'
        self.assertEqual(self.client.post(reverse('accion_jornada',args=[r.pk]),data).status_code,302)
        r.refresh_from_db()
        self.assertEqual(CorreccionEvento.objects.count(),4)
        self.assertEqual(r.horas_trabajadas,8)
        self.assertFalse(r.verificado_contabilidad)
        self.assertFalse(detalle_jornada(r)['propuestas_eventos'])
        revisar(r,self.actor,'APROBADO');r.refresh_from_db()
        self.assertTrue(r.verificado_contabilidad)

    def test_incompletas_y_exceso_solo_proponen_el_ingreso(self):
        for cantidad in [1,2,3,5]:
            with self.subTest(cantidad=cantidad):
                MarcacionBiometrica.objects.all().delete()
                ResumenAsistenciaDiaria.objects.all().delete()
                marcas=[self.marca(time(8+i)) for i in range(cantidad)]
                d=detalle_jornada(self.enviar())
                self.assertEqual(d['propuestas_eventos'],{marcas[0].pk:'ENTRADA'})

    def test_marcas_duplicadas_no_generan_cuatro_eventos(self):
        for h in [time(8),time(12),time(12),time(17)]: self.marca(h)
        d=detalle_jornada(self.enviar())
        self.assertEqual(len(d['propuestas_eventos']),1)
        self.assertNotIn('SALIDA',d['propuestas_eventos'].values())

    def test_madrugada_y_noche_no_se_asumen_una_jornada_por_tener_cuatro_marcas(self):
        for h in [time(0,14),time(7,35),time(19,52),time(23,15)]:self.marca(h)
        d=detalle_jornada(self.enviar())
        self.assertFalse(d['propuestas_eventos'])

    def test_conserva_eventos_corregidos_y_descarta_invalidas(self):
        marcas=self.cuatro()
        CorreccionEvento.objects.create(marcacion=marcas[1],tipo_evento='SALIDA',motivo='Confirmado por contadora',responsable=self.actor)
        r=self.enviar();d=detalle_jornada(r)
        self.assertNotIn(marcas[1].pk,d['propuestas_eventos'])
        self.assertEqual(d['propuestas_eventos'],{marcas[0].pk:'ENTRADA'})
        self.assertEqual(CorreccionEvento.objects.get().tipo_evento,'SALIDA')

    def test_nocturna_se_agrupa_por_programacion_y_no_por_medianoche(self):
        noche=TurnoHorario.objects.create(nombre='Noche',hora_entrada=time(20),hora_salida=time(6))
        programar_horarios(self.persona,self.dia,self.dia,[5],noche,'Programado',self.actor)
        self.marca(time(19,58));self.marca(time(23));self.marca(time(0),self.dia+timedelta(days=1));self.marca(time(6,5),self.dia+timedelta(days=1))
        r=self.enviar();d=detalle_jornada(r)
        self.assertEqual(len(d['marcas']),4)
        self.assertEqual(len(d['propuestas_eventos']),4)
        self.assertLess(r.ultima_salida,r.primera_entrada)
        self.assertEqual(ResumenAsistenciaDiaria.objects.count(),1)

    def test_periodo_y_detalle_muestran_preseleccion_y_original_real(self):
        self.cuatro();r=self.enviar()
        res=self.client.get(reverse('dashboard'),{'vista':'asistencia','desde':str(self.dia),'hasta':str(self.dia),'persona_dni':self.persona.dni,'detalle':r.pk})
        self.assertContains(res,'Eventos propuestos · Pendiente de validar')
        self.assertContains(res,'Confirmar eventos y validar jornada')
        self.assertContains(res,'value="ENTRADA" selected')
        self.assertFalse(CorreccionEvento.objects.exists())

    def test_jornada_aprobada_no_recibe_sugerencias(self):
        self.cuatro();r=self.enviar()
        r.verificado_contabilidad=True;r.save(update_fields=['verificado_contabilidad'])
        self.assertFalse(detalle_jornada(r)['propuestas_eventos'])

    def test_turno_nocturno_salida_aislada_no_se_propone_como_ingreso(self):
        noche=TurnoHorario.objects.create(nombre='Noche',hora_entrada=time(20),hora_salida=time(6))
        programar_horarios(self.persona,self.dia,self.dia,[5],noche,'Programado',self.actor)
        self.marca(time(6),self.dia+timedelta(days=1))
        r=self.enviar()
        self.assertFalse(detalle_jornada(r)['propuestas_eventos'])

    def test_cerrada_no_ofrece_propuestas_y_no_se_puede_confirmar(self):
        self.cuatro();r=self.enviar()
        CierreAsistencia.objects.create(fecha_inicio=self.dia,fecha_fin=self.dia,total_jornadas=1)
        self.assertFalse(detalle_jornada(r)['propuestas_eventos'])
        respuesta=self.client.post(reverse('accion_jornada',args=[r.pk]),{'accion':'corregir_eventos'})
        self.assertEqual(respuesta.status_code,302)
        self.assertFalse(CorreccionEvento.objects.exists())

    def test_marca_invalidada_no_cuenta_como_cuarta(self):
        marcas=self.cuatro()
        marcas[-1].es_valida=False;marcas[-1].save()
        d=detalle_jornada(self.enviar())
        self.assertEqual(d['propuestas_eventos'],{marcas[0].pk:'ENTRADA'})
