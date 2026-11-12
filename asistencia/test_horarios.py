from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from asistencia.models import Trabajador, TurnoHorario, ProgramacionHorario, ResumenAsistenciaDiaria, IdentidadBiometrica, MarcacionBiometrica, CierreAsistencia, RevisionAsistencia
from asistencia.forms_horarios import TurnoConfirmadoForm
from asistencia.services.horarios import programar_horarios, actualizar_tardanza
from asistencia.services.revision import detalle_jornada
from asistencia.services.transferencia import pasar_a_asistencia
from core.models import Usuario


class HorariosTests(TestCase):
    def setUp(self):
        self.actor=Usuario.objects.create_user('contabilidad_horarios',email='horarios@example.invalid',dni='10101010',rol='CONTADORA')
        self.persona=Trabajador.objects.create(nombre_completo='Abisag Prueba',dni='20202020',area='Boletería',sede='CAJAMARCA')
        self.identidad=IdentidadBiometrica.objects.create(trabajador=self.persona,sede='CAJAMARCA',equipo='1',codigo='42')
        self.manana=TurnoHorario.objects.create(nombre='Mañana',hora_entrada=time(6),hora_salida=time(15),tolerancia_minutos=10)
        self.tarde=TurnoHorario.objects.create(nombre='Tarde',hora_entrada=time(14),hora_salida=time(23),tolerancia_minutos=10)
        self.dia=date(2026,8,1)
        self.client.force_login(self.actor)

    def marcas(self,dia,horas):
        for i,hora in enumerate(horas):
            fecha=dia+timedelta(days=1) if i and hora < horas[0] else dia
            MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad,fecha_hora=timezone.make_aware(datetime.combine(fecha,hora)),tipo_evento=['ENTRADA','SALIDA_REFRIGERIO','RETORNO_REFRIGERIO','SALIDA'][i])

    def programar(self,desde=None,hasta=None,turno=None,dias=None):
        return programar_horarios(self.persona,desde or self.dia,hasta or self.dia,dias or list(range(7)),turno or self.tarde,'Programación confirmada por Contabilidad',self.actor)

    def test_programa_futuro_sin_crear_jornadas_y_respeta_dias_semanales(self):
        self.programar(hasta=self.dia+timedelta(days=6),dias=[0,2,4])
        self.assertEqual(ProgramacionHorario.objects.count(),3)
        self.assertFalse(ResumenAsistenciaDiaria.objects.exists())
        self.assertTrue(all(p.fecha.weekday() in [0,2,4] for p in ProgramacionHorario.objects.all()))

    def test_rotacion_por_rangos_y_transferencia_usa_horario_del_dia(self):
        self.programar(turno=self.manana)
        self.programar(desde=self.dia+timedelta(days=1),hasta=self.dia+timedelta(days=1))
        self.marcas(self.dia,[time(6),time(10),time(11),time(15)])
        self.marcas(self.dia+timedelta(days=1),[time(14),time(17),time(18),time(23)])
        pasar_a_asistencia([self.persona.pk],self.dia,self.dia+timedelta(days=1),self.actor)
        self.assertEqual(list(ResumenAsistenciaDiaria.objects.order_by('fecha').values_list('turno_aplicado_id',flat=True)),[self.manana.pk,self.tarde.pk])

    def test_corrige_tardanza_sin_cambiar_marcas_y_exige_nueva_aprobacion(self):
        self.marcas(self.dia,[time(14,2,51),time(17,23,28),time(18,15,4),time(23,11,38)])
        r=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=self.dia,primera_entrada=time(14,2,51),ultima_salida=time(23,11,38),turno_aplicado=self.manana,estado='TARDANZA',minutos_tardanza=482,verificado_contabilidad=True,estado_revision='APROBADO',horas_trabajadas=Decimal('8.29'))
        antes=list(MarcacionBiometrica.objects.values_list('pk','fecha_hora','tipo_evento'))
        resultado=self.programar()
        r.refresh_from_db()
        self.assertEqual(r.minutos_tardanza,0)
        self.assertEqual(r.estado,'ASISTIO')
        self.assertFalse(r.verificado_contabilidad)
        self.assertEqual(resultado['reabiertas'],1)
        self.assertEqual(antes,list(MarcacionBiometrica.objects.values_list('pk','fecha_hora','tipo_evento')))
        self.assertTrue(RevisionAsistencia.objects.filter(accion='Horario programado',detalle__contains='anterior: Mañana').exists())

    def test_tolerancia_limites_y_atraso_total(self):
        self.tarde.evaluar_tardanzas = True
        self.tarde.save(update_fields=['evaluar_tardanzas'])
        self.manana.evaluar_tardanzas = True
        self.manana.save(update_fields=['evaluar_tardanzas'])
        self.marcas(self.dia,[time(14,10),time(17),time(18),time(23)])
        r=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=self.dia,primera_entrada=time(14,10),ultima_salida=time(23),turno_aplicado=self.tarde)
        actualizar_tardanza(r)
        self.assertEqual(r.minutos_tardanza,0)
        marca=MarcacionBiometrica.objects.get(tipo_evento='ENTRADA')
        marca.fecha_hora+=timedelta(seconds=1);marca.save()
        actualizar_tardanza(r)
        self.assertEqual(r.minutos_tardanza,10)

    def test_cierre_en_medio_del_rango_revierte_todo(self):
        fecha=self.dia+timedelta(days=1)
        CierreAsistencia.objects.create(fecha_inicio=fecha,fecha_fin=fecha,cerrado_por=self.actor,total_jornadas=0)
        with self.assertRaises(ValidationError): self.programar(hasta=fecha)
        self.assertFalse(ProgramacionHorario.objects.exists())
        self.assertFalse(RevisionAsistencia.objects.exists())

    def test_repetir_no_reabre_una_jornada_ya_aprobada_con_mismo_turno(self):
        self.programar()
        r=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=self.dia,turno_aplicado=self.tarde,verificado_contabilidad=True)
        resultado=self.programar()
        r.refresh_from_db()
        self.assertTrue(r.verificado_contabilidad)
        self.assertEqual(resultado['sin_cambios'],1)

    def test_sin_horario_no_presenta_cero_como_puntualidad(self):
        self.marcas(self.dia,[time(14),time(17),time(18),time(23)])
        r=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=self.dia,primera_entrada=time(14),ultima_salida=time(23),minutos_tardanza=362,estado='TARDANZA')
        d=detalle_jornada(r)
        self.assertFalse(d['tardanza_confirmada'])
        self.assertEqual(d['estado_asistencia_visible'],'Horario por confirmar')
        actualizar_tardanza(r,d)
        self.assertEqual(r.estado,'POR_REVISAR')

    def test_turno_nocturno_une_salida_del_dia_siguiente_y_calcula_tardanza(self):
        noche=TurnoHorario.objects.create(nombre='Noche',hora_entrada=time(20),hora_salida=time(6),tolerancia_minutos=10)
        self.programar(turno=noche)
        self.marcas(self.dia,[time(20,5),time(23),time(0),time(6)])
        pasar_a_asistencia([self.persona.pk],self.dia,self.dia,self.actor)
        r=ResumenAsistenciaDiaria.objects.get()
        d=detalle_jornada(r)
        self.assertTrue(d['completa'])
        self.assertEqual(d['fin_consulta'].date(),self.dia+timedelta(days=1))
        self.assertEqual(r.minutos_tardanza,0)
        self.assertEqual(len(d['marcas']),4)

    def test_post_y_catalogo_validan_datos_y_permisos(self):
        data={'trabajador':self.persona.pk,'desde':str(self.dia),'hasta':str(self.dia),'dias':['5'],'turno':self.tarde.pk,'motivo':'Confirmado','confirmado':'on'}
        res=self.client.post(reverse('programar_horarios'),data)
        self.assertEqual(res.status_code,302)
        self.assertEqual(self.client.get(res.url).status_code,200)
        self.assertTrue(ProgramacionHorario.objects.exists())
        data.pop('confirmado')
        self.assertContains(self.client.post(reverse('programar_horarios'),data),'Este campo es obligatorio')
        self.actor.rol='CONDUCTOR';self.actor.save()
        self.assertEqual(self.client.get(reverse('programar_horarios')).status_code,403)
        self.assertEqual(self.client.post(reverse('programar_horarios'),data).status_code,403)

    def test_catalogo_rechaza_refrigerio_fuera_del_turno(self):
        data={'nombre':'Nuevo','hora_entrada':'20:00','hora_salida':'06:00','tolerancia_minutos':10,'hora_inicio_refrigerio':'12:00','hora_fin_refrigerio':'13:00'}
        self.assertFalse(TurnoConfirmadoForm(data).is_valid())
        data.update(hora_inicio_refrigerio='23:00',hora_fin_refrigerio='00:00')
        self.assertTrue(TurnoConfirmadoForm(data).is_valid())

    def test_crear_horario_desde_pantalla(self):
        data={'accion':'crear_turno','nuevo-nombre':'Cajamarca tarde confirmado','nuevo-hora_entrada':'14:00','nuevo-hora_salida':'23:00','nuevo-tolerancia_minutos':10}
        self.assertEqual(self.client.post(reverse('programar_horarios'),data).status_code,302)
        self.assertTrue(TurnoHorario.objects.filter(nombre=data['nuevo-nombre']).exists())

    def test_horario_agrupa_sin_evaluar_tardanza_por_defecto(self):
        self.assertFalse(self.tarde.evaluar_tardanzas)
        r=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=self.dia,turno_aplicado=self.tarde)
        inicio=timezone.make_aware(datetime.combine(self.dia,time(14,45)))
        d={'turno':self.tarde,'completa':True,'tramos':[{'inicio':inicio}]}
        actualizar_tardanza(r,d)
        self.assertEqual(r.minutos_tardanza,0)
        self.assertEqual(r.estado,'ASISTIO')
        self.tarde.evaluar_tardanzas=True
        actualizar_tardanza(r,d)
        self.assertEqual(r.minutos_tardanza,45)
        self.assertEqual(r.estado,'TARDANZA')

    def test_configurar_puntualidad_desde_catalogo(self):
        response=self.client.post(reverse('programar_horarios'),{'accion':'puntualidad_turno','turno_id':self.tarde.pk,'evaluar_tardanzas':'si'})
        self.assertEqual(response.status_code,302)
        self.tarde.refresh_from_db()
        self.assertTrue(self.tarde.evaluar_tardanzas)
        self.client.post(reverse('programar_horarios'),{'accion':'puntualidad_turno','turno_id':self.tarde.pk})
        self.tarde.refresh_from_db()
        self.assertFalse(self.tarde.evaluar_tardanzas)

    def test_referencia_opcional_y_confirmacion_obligatoria(self):
        from asistencia.forms_horarios import ProgramarHorarioForm
        datos={'trabajador':self.persona.pk,'desde':str(self.dia),'hasta':str(self.dia),'dias':[self.dia.weekday()],'turno':self.tarde.pk,'motivo':'','confirmado':'on'}
        form=ProgramarHorarioForm(datos)
        self.assertTrue(form.is_valid(),form.errors)
        resultado=programar_horarios(self.persona,self.dia,self.dia,[self.dia.weekday()],self.tarde,'',self.actor)
        self.assertEqual(resultado['programadas'],1)
        datos.pop('confirmado')
        self.assertFalse(ProgramarHorarioForm(datos).is_valid())
