"""Reglas de autorización de zonas, permisos y pagos de personal."""
import uuid
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from asistencia.models import Trabajador, ResumenAsistenciaDiaria, IncidenciaAsistencia
from .models import Perfil, Comision, Zona, Solicitud, Pago, Registro
from . import tests as base_tests


class PanelOperativoTests(TestCase):
    setUp = base_tests.AppTests.setUp
    post = base_tests.AppTests.post
    mark = base_tests.AppTests.mark

    def personal(self, area='MECANICA'):
        self.p.conductor=None;self.p.save()
        self.user.rol='ADMINISTRATIVO';self.user.save(update_fields=['rol'])
        self.worker.area=area;self.worker.save()

    def gestor(self):
        u=get_user_model().objects.create_user(username='gestor_panel',dni='55555555',rol='CONTADORA',email='gestor@example.invalid')
        p=Perfil.objects.create(usuario=u)
        self.client.force_login(u)
        return u,p

    def test_comision_sin_gps_no_requiere_excepcion_facial(self):
        self.personal()
        self.p.requiere_rostro=True;self.p.save()
        Comision.objects.create(perfil=self.p,motivo='Reparación en campo',desde=self.now-timedelta(hours=1),hasta=self.now+timedelta(hours=1),autorizada_por=self.user)
        data={'id':str(uuid.uuid4()),'tipo':'ENTRADA','capturada':self.now.isoformat()}
        response=self.post('marcar',data)
        self.assertEqual(response.status_code,200,response.content)
        registro=Registro.objects.get()
        self.assertIsNone(registro.latitud)
        self.assertIsNotNone(registro.comision_id)
        self.assertFalse(registro.facial)

    def test_comision_vencida_no_exime_gps(self):
        Comision.objects.create(perfil=self.p,motivo='Terminada',desde=self.now-timedelta(hours=2),hasta=self.now-timedelta(hours=1),autorizada_por=self.user)
        response=self.post('marcar',{'id':str(uuid.uuid4()),'tipo':'ENTRADA','capturada':self.now.isoformat()})
        self.assertEqual(response.status_code,400)
        self.assertFalse(Registro.objects.exists())

    def test_zona_area_no_autoriza_otra_area_misma_ciudad(self):
        self.personal()
        Zona.objects.update(sede='Chiclayo',area='AUXILIAR DE VENTAS')
        self.assertEqual(self.post('marcar',self.mark()).status_code,422)
        Zona.objects.update(area='mecanica')
        self.assertEqual(self.post('marcar',self.mark()).status_code,200)

    def test_permiso_aprobado_registra_situacion_y_bloquea_asistencia(self):
        self.personal()
        u,actor=self.gestor()
        dia=timezone.localdate(timezone=timezone.get_fixed_timezone(-300))
        s=Solicitud.objects.create(perfil=self.p,tipo='PERMISO',desde=dia,hasta=dia,detalle='Cita médica todo el día')
        from .gestion import gestionar
        from django.db import transaction
        with transaction.atomic():
            gestionar('revisar_solicitud',actor,{'id':s.pk,'aprobar':True})
        s.refresh_from_db();self.assertEqual(s.estado,'APROBADO')
        resumen=ResumenAsistenciaDiaria.objects.get(trabajador=self.worker,fecha=dia)
        self.assertEqual(resumen.estado,'PERMISO')
        self.assertEqual(resumen.estado_revision,'APROBADO')
        self.assertTrue(IncidenciaAsistencia.objects.filter(resumen=resumen,tipo='PERMISO',aprobado_por=u).exists())
        response=self.post('marcar',self.mark())
        self.assertEqual(response.status_code,409,response.content)
        self.assertFalse(Registro.objects.exists())

    def test_permiso_rechazado_no_bloquea_y_no_crea_situacion(self):
        self.personal()
        _,actor=self.gestor()
        dia=self.now.date()
        s=Solicitud.objects.create(perfil=self.p,tipo='PERMISO',desde=dia,hasta=dia,detalle='Solicitud no autorizada')
        from .gestion import gestionar
        from django.db import transaction
        with transaction.atomic():
            gestionar('revisar_solicitud',actor,{'id':s.pk,'aprobar':False})
        self.assertFalse(IncidenciaAsistencia.objects.exists())
        self.assertEqual(self.post('marcar',self.mark()).status_code,200)

    def test_pago_personal_sin_referencia_visible_en_su_app(self):
        self.personal()
        self.gestor()
        response=self.client.post('/movil/',{'accion':'pago','perfil':self.p.pk,'desde':self.now.date(),'hasta':self.now.date(),'monto':'150.50'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(Pago.objects.get().perfil_id,self.p.pk)
        pagos=self.post('inicio').json()['pagos']
        self.assertEqual(len(pagos),1)
        self.assertEqual(pagos[0]['monto'],'150.50')

    def test_area_ventas_asigna_funcion_sin_selector(self):
        self.personal('AUXILIAR DE VENTAS')
        self.assertEqual(self.post('inicio').json()['perfil']['rol'],'BOLETERIA')
        self.user.refresh_from_db();self.assertEqual(self.user.rol,'BOLETERIA')

    def test_habilitacion_prioriza_area_sobre_funcion_manual(self):
        self.gestor()
        t=Trabajador.objects.create(nombre_completo='VENTAS PRUEBA',dni='33333333',area='AUXILIAR DE VENTAS',sede='CHICLAYO')
        self.client.post('/movil/',{'accion':'habilitar','persona':f'trabajador:{t.pk}','funcion_app':'ADMINISTRATIVO'})
        t.refresh_from_db();self.assertEqual(t.usuario.rol,'BOLETERIA')

    def test_pago_no_se_duplica_al_reenviar_formulario(self):
        self.personal();self.gestor()
        d={'accion':'pago','perfil':self.p.pk,'desde':self.now.date(),'hasta':self.now.date(),'monto':'20','id_pago':uuid.uuid4().hex}
        self.client.post('/movil/',d)
        response=self.client.post('/movil/',d)
        self.assertContains(response,'Este pago ya está registrado')
        self.assertEqual(Pago.objects.count(),1)

    def test_panel_no_lista_perfiles_administrativos_sin_area(self):
        _,actor=self.gestor()
        response=self.client.get('/movil/')
        ids={p.pk for p in response.context['perfiles']}
        self.assertNotIn(actor.pk,ids)
        self.assertIn(self.p.pk,ids)
        self.assertNotContains(response,'Marcaciones de asistencia')
        self.assertNotContains(response,'name="sin_rostro"')
        self.assertNotContains(response,'name="referencia"')

    def test_editar_activar_eliminar_zona_respeta_historial(self):
        self.gestor()
        z=Zona.objects.get()
        response=self.client.post('/movil/',{'accion':'editar_zona','zona':z.pk,'nombre':'Taller','alcance':'area','sede':'CHICLAYO','area':'MECANICA','latitud':-6.77,'longitud':-79.84,'radio':80})
        self.assertEqual(response.status_code,200)
        z.refresh_from_db();self.assertEqual(z.area,'MECANICA');self.assertEqual(z.radio,80)
        self.client.post('/movil/',{'accion':'desactivar_zona','zona':z.pk});z.refresh_from_db();self.assertFalse(z.activa)
        self.client.post('/movil/',{'accion':'activar_zona','zona':z.pk});z.refresh_from_db();self.assertTrue(z.activa)
        Registro.objects.create(perfil=self.p,tipo='ENTRADA',jornada=self.now.date(),zona=z)
        response=self.client.post('/movil/',{'accion':'eliminar_zona','zona':z.pk})
        self.assertContains(response,'Esta zona tiene marcaciones')
        self.assertTrue(Zona.objects.filter(pk=z.pk).exists())
        libre=Zona.objects.create(nombre='Sin uso',sede='CHICLAYO',latitud=0,longitud=0)
        self.client.post('/movil/',{'accion':'eliminar_zona','zona':libre.pk})
        self.assertFalse(Zona.objects.filter(pk=libre.pk).exists())
