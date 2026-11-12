from datetime import date, datetime, time, timedelta
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from core.models import Usuario
from asistencia.models import Trabajador, IdentidadBiometrica, MarcacionBiometrica, ResumenAsistenciaDiaria, CierreAsistencia, CorreccionEvento
from asistencia.services.duplicadas import revisar_duplicada, EXCLUIR, RESTAURAR
from asistencia.services.revision import detalle_jornada


class DuplicadasTests(TestCase):
    def setUp(self):
        self.actor=Usuario.objects.create_user('duplicadas_prueba',email='duplicadas@example.invalid',dni='11111111',rol='CONTADORA')
        self.p=Trabajador.objects.create(nombre_completo='Persona Duplicadas',dni='22222222',area='Administración')
        self.i=IdentidadBiometrica.objects.create(trabajador=self.p,sede='CHICLAYO',equipo='104',codigo='123')
        self.dia=date(2026,8,3)
        self.marcas=[MarcacionBiometrica.objects.create(identidad_biometrica=self.i,fecha_hora=timezone.make_aware(datetime.combine(self.dia,h)),tipo_evento='SIN_CLASIFICAR') for h in [time(9,25,45),time(13,44,40),time(13,44,42),time(14,48,48),time(19,14,39)]]
        self.r=ResumenAsistenciaDiaria.objects.create(trabajador=self.p,fecha=self.dia,primera_entrada=time(9,25,45),ultima_salida=time(19,14,39),marcaciones_publicadas=[m.pk for m in self.marcas])
        self.client.force_login(self.actor)
        self.url=reverse('accion_jornada',args=[self.r.pk])

    def test_excluir_es_reversible_y_preserva_fuente_sin_confirmar_eventos(self):
        fuente=self.marcas[2];antes=(fuente.fecha_hora,fuente.tipo_evento,fuente.origen)
        revisar_duplicada(self.r,self.actor,fuente.pk)
        fuente.refresh_from_db();self.r.refresh_from_db();d=detalle_jornada(self.r)
        self.assertFalse(fuente.es_valida)
        self.assertEqual((fuente.fecha_hora,fuente.tipo_evento,fuente.origen),antes)
        self.assertEqual(len(d['propuestas_eventos']),4)
        self.assertFalse(d['completa']);self.assertFalse(self.r.verificado_contabilidad)
        self.assertFalse(CorreccionEvento.objects.exists())
        fila=next(f for f in d['cuadro_excel']['filas'] if f['marcacion_id']==fuente.pk)
        self.assertTrue(fila['excluida_duplicada'])
        self.assertTrue(self.r.historial_revision.filter(accion=EXCLUIR,marcacion=fuente,responsable=self.actor).exists())
        revisar_duplicada(self.r,self.actor,fuente.pk,restaurar=True)
        fuente.refresh_from_db();self.assertTrue(fuente.es_valida)
        self.assertTrue(self.r.historial_revision.filter(accion=RESTAURAR).exists())
        self.assertEqual(MarcacionBiometrica.objects.count(),5)

    def test_no_excluye_dos_marcas_del_par_ni_por_post_repetido(self):
        revisar_duplicada(self.r,self.actor,self.marcas[2].pk)
        for pk in [self.marcas[1].pk,self.marcas[2].pk,self.marcas[0].pk]:
            with self.assertRaises(ValidationError):revisar_duplicada(self.r,self.actor,pk)
        self.assertEqual(MarcacionBiometrica.objects.filter(es_valida=False).count(),1)

    def test_no_afecta_otro_grupo_y_no_restaura_invalidaciones_ajenas(self):
        m=MarcacionBiometrica.objects.create(identidad_biometrica=self.i,fecha_hora=self.marcas[2].fecha_hora+timedelta(seconds=1),es_valida=False)
        with self.assertRaises(ValidationError):revisar_duplicada(self.r,self.actor,m.pk,restaurar=True)
        self.r.marcaciones_publicadas.append(m.pk);self.r.save()
        with self.assertRaises(ValidationError):revisar_duplicada(self.r,self.actor,m.pk,restaurar=True)

    def test_exclusion_reabre_y_cierre_no_permite_cambios(self):
        self.r.verificado_contabilidad=True;self.r.save(update_fields=['verificado_contabilidad'])
        revisar_duplicada(self.r,self.actor,self.marcas[2].pk);self.r.refresh_from_db()
        self.assertFalse(self.r.verificado_contabilidad)
        CierreAsistencia.objects.create(fecha_inicio=self.dia,fecha_fin=self.dia,total_jornadas=1)
        with self.assertRaises(ValidationError):revisar_duplicada(self.r,self.actor,self.marcas[2].pk,restaurar=True)
        self.marcas[2].refresh_from_db();self.assertFalse(self.marcas[2].es_valida)

    def test_ui_post_y_permisos(self):
        params={'vista':'asistencia','desde':str(self.dia),'hasta':str(self.dia),'detalle':self.r.pk}
        self.assertContains(self.client.get(reverse('dashboard'),params),'Duplicada · No computar')
        self.client.post(self.url,{'accion':'excluir_duplicada','marcacion_id':self.marcas[2].pk})
        self.assertContains(self.client.get(reverse('dashboard'),params),'Restaurar')
        self.actor.rol='BOLETERIA';self.actor.save()
        self.assertEqual(self.client.post(self.url,{'accion':'restaurar_duplicada','marcacion_id':self.marcas[2].pk}).status_code,403)

    def test_recalcula_eventos_confirmados_y_al_restaurar_no_deja_horas_obsoletas(self):
        for marca,tipo in zip(self.marcas,['ENTRADA','SALIDA_REFRIGERIO','SALIDA_REFRIGERIO','RETORNO_REFRIGERIO','SALIDA']):
            marca.tipo_evento=tipo;marca.save(update_fields=['tipo_evento'])
        revisar_duplicada(self.r,self.actor,self.marcas[2].pk)
        self.r.refresh_from_db()
        self.assertEqual(detalle_jornada(self.r)['trabajo_reconstruido'],'08:44:46')
        self.assertGreater(self.r.horas_trabajadas,8)
        revisar_duplicada(self.r,self.actor,self.marcas[2].pk,restaurar=True)
        self.r.refresh_from_db()
        self.assertFalse(detalle_jornada(self.r)['completa'])
        self.assertEqual(self.r.horas_trabajadas,0)
