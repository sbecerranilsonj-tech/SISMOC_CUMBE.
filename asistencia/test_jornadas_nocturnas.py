from datetime import date, datetime, time, timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from asistencia.models import Trabajador, IdentidadBiometrica, MarcacionBiometrica, ResumenAsistenciaDiaria, TurnoHorario, CargaArchivoAsistencia, CorreccionEvento, CierreAsistencia, IncidenciaAsistencia, ProgramacionHorario
from asistencia.services.horarios import programar_horarios
from asistencia.services.revision import detalle_jornada
from asistencia.services.revision_trabajador import detalles_en_lote, validar_periodo
from core.models import Usuario


class JornadasNocturnasTests(TestCase):
    def setUp(self):
        self.actor=Usuario.objects.create_user('noche_prueba',email='noche@example.invalid',dni='10101010',rol='CONTADORA')
        self.persona=Trabajador.objects.create(nombre_completo='Persona Nocturna',dni='20202020',area='Operaciones',sede='CHICLAYO')
        self.i=IdentidadBiometrica.objects.create(trabajador=self.persona,sede='CHICLAYO',equipo='1',codigo='100')
        self.turno=TurnoHorario.objects.create(nombre='Nocturno confirmado',hora_entrada=time(20),hora_salida=time(7))
        self.carga=CargaArchivoAsistencia.objects.create(nombre_archivo_original='Prueba agosto.xlsx')
        self.dia=date(2026,8,2)
        self.marcas=[]
        for fecha,hora in [(self.dia,time(21,2,7)),(self.dia,time(23,8,43)),(self.dia,time(23,53,45)),(self.dia+timedelta(days=1),time(7,36,18)),(self.dia+timedelta(days=1),time(19,49))]:
            self.marcas.append(MarcacionBiometrica.objects.create(identidad_biometrica=self.i,fecha_hora=timezone.make_aware(datetime.combine(fecha,hora)),tipo_evento='SIN_CLASIFICAR',carga_origen=self.carga))
        self.r=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=self.dia,primera_entrada=time(21,2,7),ultima_salida=time(23,53,45),marcaciones_publicadas=[m.pk for m in self.marcas[:3]])
        self.s=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=self.dia+timedelta(days=1),primera_entrada=time(7,36,18),ultima_salida=time(19,49),marcaciones_publicadas=[m.pk for m in self.marcas[3:]])

    def programar(self):
        return programar_horarios(self.persona,self.dia,self.dia,[self.dia.weekday()],self.turno,'Horario confirmado para prueba',self.actor)

    def test_reagrupa_existentes_sin_cambiar_fuentes_ni_otra_entrada(self):
        originales=list(MarcacionBiometrica.objects.values_list('pk','fecha_hora','tipo_evento'))
        result=self.programar();self.r.refresh_from_db();self.s.refresh_from_db()
        self.assertEqual(result['reagrupadas'],1)
        self.assertEqual(self.r.marcaciones_publicadas,[m.pk for m in self.marcas[:4]])
        self.assertEqual(self.s.marcaciones_publicadas,[self.marcas[4].pk])
        self.assertEqual(self.s.primera_entrada,time(19,49))
        self.assertEqual(self.r.ultima_salida,time(7,36,18))
        self.assertFalse(self.r.verificado_contabilidad)
        d=detalle_jornada(self.r)
        self.assertTrue(d['cruza_medianoche'])
        self.assertEqual(len(d['propuestas_eventos']),4)
        self.assertFalse(d['completa'])
        self.assertFalse(CorreccionEvento.objects.exists())
        self.assertEqual(originales,list(MarcacionBiometrica.objects.values_list('pk','fecha_hora','tipo_evento')))
        self.assertEqual(len(detalles_en_lote([self.r,self.s])[0]['marcas']),4)

    def test_confirma_secuencia_calcula_y_no_aprueba(self):
        self.programar();self.r.refresh_from_db()
        propuestas=detalle_jornada(self.r)['propuestas_eventos']
        validar_periodo([self.r],propuestas,{pk:'SIN_CLASIFICAR' for pk in propuestas},None,'Validación de prueba',self.actor)
        self.r.refresh_from_db();d=detalle_jornada(self.r)
        self.assertEqual(d['trabajo_reconstruido'],'09:49:09')
        self.assertEqual(d['refrigerio'],'00:45:02')
        self.assertFalse(self.r.verificado_contabilidad)
        self.assertTrue(d['completa'])

    def test_no_incorpora_marcas_de_otro_archivo(self):
        otra=CargaArchivoAsistencia.objects.create(nombre_archivo_original='Otra carga.xlsx')
        ajena=MarcacionBiometrica.objects.create(identidad_biometrica=self.i,fecha_hora=timezone.make_aware(datetime.combine(self.dia+timedelta(days=1),time(5))),tipo_evento='SIN_CLASIFICAR',carga_origen=otra)
        self.programar();self.r.refresh_from_db()
        self.assertNotIn(ajena.pk,self.r.marcaciones_publicadas)

    def test_cierre_de_manana_revierte_programacion_y_grupos(self):
        CierreAsistencia.objects.create(fecha_inicio=self.s.fecha,fecha_fin=self.s.fecha,total_jornadas=1)
        with self.assertRaises(ValidationError):self.programar()
        self.r.refresh_from_db()
        self.assertEqual(len(self.r.marcaciones_publicadas),3)
        self.assertFalse(ProgramacionHorario.objects.exists())

    def test_incidencias_y_entradas_confirmadas_no_se_mezclan(self):
        IncidenciaAsistencia.objects.create(resumen=self.s,tipo='PERMISO',motivo='Permiso prueba',creado_por=self.actor)
        with self.assertRaises(ValidationError):self.programar()
        self.assertFalse(ProgramacionHorario.objects.exists())

    def test_repetir_no_modifica_una_aprobacion_posterior(self):
        self.programar();self.r.refresh_from_db()
        self.r.verificado_contabilidad=True;self.r.save(update_fields=['verificado_contabilidad'])
        self.programar();self.r.refresh_from_db()
        self.assertTrue(self.r.verificado_contabilidad)

    def test_noches_consecutivas_reagrupan_todo_el_rango_y_no_solo_la_primera(self):
        nuevas=[]
        for offset,hora in [(1,time(23,19,53)),(2,time(0,14,49)),(2,time(7,35,22)),(2,time(19,52,17)),(2,time(23,15,2)),(3,time(0,8,59)),(3,time(7,4,10))]:
            nuevas.append(MarcacionBiometrica.objects.create(identidad_biometrica=self.i,fecha_hora=timezone.make_aware(datetime.combine(self.dia+timedelta(days=offset),hora)),tipo_evento='SIN_CLASIFICAR',carga_origen=self.carga))
        self.s.marcaciones_publicadas.append(nuevas[0].pk);self.s.ultima_salida=time(23,19,53);self.s.save()
        t=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=self.dia+timedelta(days=2),primera_entrada=time(0,14,49),ultima_salida=time(23,15,2),marcaciones_publicadas=[m.pk for m in nuevas[1:5]])
        u=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=self.dia+timedelta(days=3),primera_entrada=time(0,8,59),ultima_salida=time(7,4,10),marcaciones_publicadas=[m.pk for m in nuevas[5:]])
        programar_horarios(self.persona,self.dia,t.fecha,list(range(7)),self.turno,'Noches confirmadas',self.actor)
        grupos=[]
        for resumen in [self.r,self.s,t]:
            resumen.refresh_from_db();d=detalle_jornada(resumen)
            self.assertEqual(len(d['marcas']),4)
            self.assertEqual(len(d['propuestas_eventos']),4)
            self.assertEqual(d['marcas'][0].fecha_local.date(),resumen.fecha)
            self.assertEqual(d['marcas'][-1].fecha_local.date(),resumen.fecha+timedelta(days=1))
            grupos.extend(m.pk for m in d['marcas'])
        self.assertEqual(len(grupos),len(set(grupos)))
        u.refresh_from_db()
        self.assertEqual(u.marcaciones_publicadas,[])
        self.assertEqual(u.estado,'POR_REVISAR')
        self.assertFalse(u.incidencias.exists())

    def test_inicio_archivo_con_salida_sin_entrada_no_bloquea_noches(self):
        madrugada=MarcacionBiometrica.objects.create(identidad_biometrica=self.i,fecha_hora=timezone.make_aware(datetime.combine(self.dia,time(7,46))),tipo_evento='SIN_CLASIFICAR',carga_origen=self.carga)
        self.r.primera_entrada=time(7,46)
        self.r.marcaciones_publicadas.insert(0,madrugada.pk)
        self.r.save()
        originales=list(MarcacionBiometrica.objects.values_list('pk','fecha_hora','tipo_evento'))
        self.programar()
        self.r.refresh_from_db()
        self.assertEqual(self.r.marcaciones_publicadas,[m.pk for m in self.marcas[:4]])
        previa=ResumenAsistenciaDiaria.objects.get(trabajador=self.persona,fecha=self.dia-timedelta(days=1))
        self.assertEqual(previa.marcaciones_publicadas,[madrugada.pk])
        d=detalle_jornada(previa)
        self.assertFalse(d['completa'])
        self.assertIn('Marcación inicial sin pareja',d['estado_asistencia_visible'])
        self.assertEqual(d['cuadro_excel']['totales']['trabajo'],'Por revisar')
        self.assertEqual(previa.horas_trabajadas,0)
        self.assertFalse(previa.verificado_contabilidad)
        self.assertEqual(originales,list(MarcacionBiometrica.objects.values_list('pk','fecha_hora','tipo_evento')))
        self.programar()
        self.assertEqual(ResumenAsistenciaDiaria.objects.filter(trabajador=self.persona,fecha=previa.fecha).count(),1)

    def test_jornada_previa_vacia_no_bloquea_inicio_incompleto(self):
        previa = ResumenAsistenciaDiaria.objects.create(
            trabajador=self.persona, fecha=self.dia-timedelta(days=1),
            marcaciones_publicadas=[], estado='POR_REVISAR')
        self.test_inicio_archivo_con_salida_sin_entrada_no_bloquea_noches()
        previa.refresh_from_db()
        self.assertTrue(previa.conceptos_editados['inicio_archivo_sin_entrada'])

    def test_completar_inicio_incompleto_con_entrada_publicada(self):
        self.test_inicio_archivo_con_salida_sin_entrada_no_bloquea_noches()
        previa=ResumenAsistenciaDiaria.objects.get(trabajador=self.persona,fecha=self.dia-timedelta(days=1))
        entrada=MarcacionBiometrica.objects.create(identidad_biometrica=self.i,fecha_hora=timezone.make_aware(datetime.combine(previa.fecha,time(20))),tipo_evento='SIN_CLASIFICAR',carga_origen=self.carga)
        previa.marcaciones_publicadas.append(entrada.pk)
        previa.save()
        programar_horarios(self.persona,previa.fecha,previa.fecha,[previa.fecha.weekday()],self.turno,'Entrada faltante recibida',self.actor)
        previa.refresh_from_db()
        self.assertNotIn('inicio_archivo_sin_entrada',previa.conceptos_editados)
        self.assertEqual(len(detalle_jornada(previa)['marcas']),2)

    def test_aviso_entrada_conflictiva_indica_fecha_y_hora(self):
        self.marcas[3].tipo_evento='ENTRADA'
        self.marcas[3].save(update_fields=['tipo_evento'])
        with self.assertRaises(ValidationError) as error:
            self.programar()
        texto=str(error.exception)
        self.assertIn('03/08/2026 a las 07:36:18',texto)
        self.assertIn('02/08/2026 al 03/08/2026',texto)
        self.assertFalse(ProgramacionHorario.objects.exists())

    def test_vigilancia_dos_marcas_incluye_refrigerio_en_base(self):
        self.persona.area='VIGILANTE'
        self.persona.save(update_fields=['area'])
        self.marcas[1].es_valida=False;self.marcas[1].save(update_fields=['es_valida'])
        self.marcas[2].es_valida=False;self.marcas[2].save(update_fields=['es_valida'])
        self.programar();self.r.refresh_from_db()
        from asistencia.services.cuadro_excel import base_jornada_segundos
        self.assertEqual(base_jornada_segundos(self.r),31500)
        d=detalle_jornada(self.r)
        self.assertEqual(set(d['propuestas_eventos'].values()),{'ENTRADA','SALIDA'})
        validar_periodo([self.r],d['propuestas_eventos'],{pk:'SIN_CLASIFICAR' for pk in d['propuestas_eventos']},None,'Validación',self.actor)
        d=detalle_jornada(self.r)
        self.assertTrue(d['completa'])
        self.assertFalse(d['falta_refrigerio'])
        self.assertEqual(d['cuadro_excel']['totales']['base'],'08:45:00')
        self.assertEqual(d['refrigerio'],'00:00:00')

    def test_vigilancia_cuatro_marcas_base_ocho_horas(self):
        self.persona.area='VIGILANTE';self.persona.save(update_fields=['area'])
        self.programar();self.r.refresh_from_db()
        self.assertEqual(detalle_jornada(self.r)['cuadro_excel']['totales']['base'],'08:00:00')

    def test_nocturnas_vigilancia_vacias_hasta_edicion_manual(self):
        from asistencia.services.revision import valores_ajustados
        self.persona.area='VIGILANTE';self.persona.save(update_fields=['area'])
        self.programar();self.r.refresh_from_db()
        d=detalle_jornada(self.r)
        validar_periodo([self.r],d['propuestas_eventos'],{pk:'SIN_CLASIFICAR' for pk in d['propuestas_eventos']},None,'Validación',self.actor)
        self.assertEqual(detalle_jornada(self.r)['cuadro_excel']['totales']['nocturnas'],'00:00:00')
        self.assertEqual(valores_ajustados(self.r)['horas_nocturnas'],0)
        self.r.conceptos_editados['horas_nocturnas']=3600
        self.assertEqual(detalle_jornada(self.r)['cuadro_excel']['totales']['nocturnas'],'01:00:00')

    def test_interruptor_nocturnas_individual_preserva_revisadas(self):
        from asistencia.services.configuracion_nocturnas import configurar_nocturnas
        from asistencia.services.reglas_jornada import nocturnas_automaticas
        from asistencia.services.revision import valores_ajustados
        self.persona.area='VIGILANTE';self.persona.save(update_fields=['area'])
        self.programar();self.r.refresh_from_db()
        d=detalle_jornada(self.r)
        validar_periodo([self.r],d['propuestas_eventos'],{pk:'SIN_CLASIFICAR' for pk in d['propuestas_eventos']},None,'Validación',self.actor)
        self.s.refresh_from_db()
        self.s.verificado_contabilidad=True;self.s.save(update_fields=['verificado_contabilidad'])
        cerrada=ResumenAsistenciaDiaria.objects.create(trabajador=self.persona,fecha=self.dia-timedelta(days=10),horas_nocturnas=8)
        CierreAsistencia.objects.create(fecha_inicio=cerrada.fecha,fecha_fin=cerrada.fecha,total_jornadas=1)
        self.assertFalse(nocturnas_automaticas(self.r))
        configurar_nocturnas(self.persona,True,self.actor)
        self.r.refresh_from_db();self.s.refresh_from_db();cerrada.refresh_from_db()
        self.assertGreater(valores_ajustados(self.r)['horas_nocturnas'],0)
        self.assertFalse(nocturnas_automaticas(self.s))
        self.assertFalse(nocturnas_automaticas(cerrada))
        self.assertTrue(self.s.verificado_contabilidad)
        self.assertFalse(self.r.verificado_contabilidad)
        self.r.conceptos_editados['horas_nocturnas']=3600;self.r.save(update_fields=['conceptos_editados'])
        configurar_nocturnas(self.persona,False,self.actor)
        self.r.refresh_from_db()
        self.assertEqual(valores_ajustados(self.r)['horas_nocturnas'],1)
