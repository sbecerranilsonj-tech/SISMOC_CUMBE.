import json
import uuid
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from asistencia.models import Trabajador, MarcacionBiometrica, PeriodoVacaciones
from conductores.models import Conductor, Importacion, Salida
from .models import *
from .views import hash_token

class AppTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(email='prueba@example.invalid',username='empleado',password='SeguroPrueba2026!',dni='12345678',rol='CONDUCTOR')
        self.worker=Trabajador.objects.get(usuario=self.user)
        self.worker.nombre_completo='ANA PEREZ PRUEBA';self.worker.area='CONDUCTORES';self.worker.sede='CHICLAYO';self.worker.save()
        self.driver=Conductor.objects.create(nombre='ANA PEREZ PRUEBA',trabajador=self.worker)
        self.p=Perfil.objects.create(usuario=self.user,trabajador=self.worker,conductor=self.driver,activado=True,dispositivo='device-prueba-123')
        Sesion.objects.create(perfil=self.p,token_hash=hash_token('token'),vence=timezone.now()+timedelta(days=1))
        self.auth={'HTTP_AUTHORIZATION':'Bearer token'}
        self.now=timezone.localtime(timezone.now())
        Zona.objects.create(nombre='Terminal',sede='CHICLAYO',latitud=-6.77,longitud=-79.84,radio=100)
    def post(self,a,d=None,auth=True):
        return self.client.post('/movil/api/'+a+'/',data=json.dumps(d or {}),content_type='application/json',**(self.auth if auth else {}))
    def trip(self):
        other=get_user_model().objects.create_user(email='prueba@example.invalid',username='dos',password='password',dni='87654321',rol='CONDUCTOR')
        c=Conductor.objects.create(nombre='JUAN TORRES PRUEBA')
        p=Perfil.objects.create(usuario=other,conductor=c,activado=True)
        lote=Importacion.objects.create(nombre='prueba.xls',huella='a'*64,inicio=self.now.date(),fin=self.now.date(),creado_por=self.user,estado='VALIDADO')
        s=Salida.objects.create(importacion=lote,fila=3,fecha=self.now.date(),hora=self.now.time(),bus='BUS1',origen='Chiclayo',destino='Cajamarca',conductor_uno=self.driver,conductor_dos=c,clave='b'*64,clave_confirmada='b'*64)
        return Operacion.objects.create(salida=s),p
    def mark(self):
        return {'id':str(uuid.uuid4()),'tipo':'ENTRADA','capturada':self.now.isoformat(),'gps_fecha':self.now.isoformat(),'latitud':-6.77,'longitud':-79.84,'precision':5}
    def test_auth_required_and_foreign_role_denied(self):
        self.assertEqual(self.post('inicio',auth=False).status_code,401)
        self.assertEqual(self.post('importar_itinerario').status_code,403)
    def test_hash_session_not_stored_plaintext(self):
        response=self.post('login',{'codigo':self.p.codigo,'password':'SeguroPrueba2026!','dispositivo':'device-prueba-123'},False)
        self.assertEqual(response.status_code,200)
        token=response.json()['token']
        self.assertFalse(Sesion.objects.filter(token_hash=token).exists())
        self.assertTrue(Sesion.objects.filter(token_hash=hash_token(token)).exists())
    def test_login_wrong_device_and_rate_limit(self):
        self.assertEqual(self.post('login',{'codigo':self.p.codigo,'password':'SeguroPrueba2026!','dispositivo':'another-device-123'},False).status_code,403)
        for _ in range(8):self.assertEqual(self.post('login',{'codigo':self.p.codigo,'password':'bad','dispositivo':'device-prueba-123'},False).status_code,401)
        self.assertEqual(self.post('login',{'codigo':self.p.codigo,'password':'bad','dispositivo':'device-prueba-123'},False).status_code,429)
    def test_activation_is_single_use(self):
        self.p.activado=False;self.p.activacion_hash=make_password('123ABC');self.p.activacion_hasta=self.now+timedelta(hours=2);self.p.save()
        d={'codigo':self.p.codigo,'activacion':'123ABC','password':'SeguroDistinto2026!','dispositivo':'device-prueba-123'}
        self.assertEqual(self.post('activar',d,False).status_code,200)
        self.assertEqual(self.post('activar',d,False).status_code,401)
    @patch('movil.views.publicar_marca')
    def test_mark_idempotent_and_server_time(self,publish):
        d=self.mark()
        self.assertEqual(self.post('marcar',d).status_code,200)
        self.assertEqual(self.post('marcar',d).status_code,200)
        self.assertEqual(Registro.objects.count(),1)
        self.assertEqual(publish.call_count,1)
    def test_mark_integrates_real_attendance(self):
        response=self.post('marcar',self.mark())
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(MarcacionBiometrica.objects.filter(origen='APP_MOVIL_GPS').count(),1)
    def test_outside_stale_inaccurate_face_not_bypassed(self):
        d=self.mark();d['latitud']=0
        self.assertEqual(self.post('marcar',d).status_code,422)
        d=self.mark();d['gps_fecha']=(self.now-timedelta(minutes=3)).isoformat()
        self.assertEqual(self.post('marcar',d).status_code,400)
        d=self.mark();d['precision']=float('nan')
        self.assertEqual(self.post('marcar',d).status_code,400)
        self.p.requiere_rostro=True;self.p.save()
        self.assertEqual(self.post('marcar',self.mark()).status_code,422)
        self.assertEqual(Registro.objects.count(),0)
    def test_offline_mark_pending_without_payroll(self):
        d=self.mark();d['offline']=True
        self.assertEqual(self.post('marcar',d).status_code,200)
        self.assertEqual(Registro.objects.get().estado,'POR_REVISAR')
        self.assertFalse(MarcacionBiometrica.objects.exists())
    def test_commission_permits_mechanic_outside_zone(self):
        Comision.objects.create(perfil=self.p,motivo='Bus averiado',desde=self.now-timedelta(hours=1),hasta=self.now+timedelta(hours=2),autorizada_por=self.user)
        d=self.mark();d.update(latitud=0,offline=True)
        self.assertEqual(self.post('marcar',d).status_code,200)
    def test_requests_previous_day_and_no_self_approval(self):
        today=timezone.localdate(timezone=self.now.tzinfo)
        # Pasado siempre requiere emergencia; mañana acepta sin exigir 24h.
        d={'tipo':'PERMISO','desde':str(today-timedelta(days=1)),'hasta':str(today),'detalle':'Cita médica programada'}
        self.assertEqual(self.post('solicitud',d).status_code,400)
        d['desde']=d['hasta']=str(today+timedelta(days=2))
        self.assertEqual(self.post('solicitud',d).status_code,200)
        self.user.rol='CONTADORA';self.user.save()
        self.assertEqual(self.post('revisar_solicitud',{'id':Solicitud.objects.get().pk,'aprobar':True}).status_code,403)
    def test_vacation_approval_applies(self):
        u=get_user_model().objects.create_user(email='prueba@example.invalid',username='contadora',dni='11111111',rol='CONTADORA')
        s=Solicitud.objects.create(perfil=Perfil.objects.create(usuario=u,trabajador=Trabajador.objects.get(usuario=u)),tipo='VACACIONES',desde=self.now.date(),hasta=self.now.date(),detalle='Vacaciones')
        self.user.rol='CONTADORA';self.user.save()
        r=self.post('revisar_solicitud',{'id':s.pk,'aprobar':True})
        self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(PeriodoVacaciones.objects.count(),1)
    def test_trip_shared_start_arrival_and_separate_rest(self):
        op,other=self.trip()
        def event(tipo):return self.post('evento',{'id':str(uuid.uuid4()),'viaje':op.pk,'tipo':tipo})
        self.assertEqual(event('INICIAR').status_code,200)
        self.assertEqual(event('INICIAR').status_code,409)
        self.assertEqual(event('LLEGADA').status_code,200)
        self.assertEqual(event('DESCANSO').status_code,200)
        self.assertFalse(Descanso.objects.filter(perfil=other).exists())
        self.assertEqual(self.post('inicio').json()['resumen']['trayectos_realizados'],1)
    def test_rest_rule_blocks_without_evidence(self):
        op,_=self.trip();ReglaDescanso.objects.create(activa=True,horas=8)
        r=self.post('evento',{'id':str(uuid.uuid4()),'viaje':op.pk,'tipo':'INICIAR'})
        self.assertEqual(r.status_code,409)
    def test_boarding_permission_compare_and_swap(self):
        op,_=self.trip()
        pasajero=Pasajero.objects.create(operacion=op,referencia='R1',nombre='Pasajero Prueba',documento='123',piso=1,asiento=1,origen='Chiclayo',destino='Cajamarca',punto='Terminal')
        self.assertEqual(self.post('pasajeros',{'viaje':op.pk}).status_code,403)
        op.permite_embarque_conductor=True;op.save()
        d={'id':str(uuid.uuid4()),'viaje':op.pk,'pasajero':pasajero.pk,'anterior':'PENDIENTE','estado':'EMBARCADO','identidad_verificada':True}
        self.assertEqual(self.post('embarcar',d).status_code,200)
        self.assertEqual(self.post('embarcar',d).status_code,200)
        d['id']=str(uuid.uuid4())
        self.assertEqual(self.post('embarcar',d).status_code,409)
    def test_own_data_isolation(self):
        op,other=self.trip()
        Registro.objects.create(perfil=other,tipo='ENTRADA',jornada=self.now.date())
        Pago.objects.create(perfil=other,desde=self.now.date(),hasta=self.now.date(),monto=100,referencia='privado',registrado_por=self.user)
        response=self.post('inicio').json()
        self.assertEqual(response['marcaciones'],[])
        self.assertEqual(response['pagos'],[])
    def test_logout_revokes_token(self):
        self.assertEqual(self.post('logout').status_code,200)
        self.assertEqual(self.post('inicio').status_code,401)

    def test_csv_repeat_preserves_boarding_and_absence(self):
        op,_=self.trip();self.user.rol='BOLETERIA';self.user.save()
        header='referencia,nombre,documento,piso,asiento,origen,destino,punto\n'
        data=header+'R1,PASAJERO,123,1,5,Chiclayo,Cajamarca,Terminal\n'
        d={'viaje':op.pk,'csv':data}
        self.assertEqual(self.post('importar_pasajeros',d).status_code,200)
        x=Pasajero.objects.get();x.estado='EMBARCADO';x.save()
        self.assertEqual(self.post('importar_pasajeros',d).status_code,200)
        x.refresh_from_db();self.assertEqual(x.estado,'EMBARCADO')
        d['csv']=header+'R2,OTRO,456,1,6,Chiclayo,Cajamarca,Terminal\n'
        self.assertEqual(self.post('importar_pasajeros',d).status_code,200)
        self.assertEqual(Pasajero.objects.count(),2)
        d['csv']=data.replace('PASAJERO','CAMBIADO')
        self.assertEqual(self.post('importar_pasajeros',d).status_code,409)
        x.refresh_from_db();self.assertEqual(x.nombre,'PASAJERO')

    def test_cancelled_trip_does_not_start_or_earn(self):
        op,_=self.trip();op.salida.anulado=True;op.salida.save()
        self.assertEqual(self.post('evento',{'id':str(uuid.uuid4()),'viaje':op.pk,'tipo':'INICIAR'}).status_code,409)
        self.assertEqual(self.post('inicio').json()['resumen']['estimado'],0)

    def test_mobile_programmed_trip_does_not_earn_in_web_calendar(self):
        from conductores.services import calendario
        op,_=self.trip();op.salida.estado_operativo='PROGRAMADO';op.salida.save()
        rows=calendario(op.salida.fecha,op.salida.fecha)[1]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row['pago_vueltas'],0)
            self.assertEqual(row['celdas'][0]['etiqueta'],'PR')

    def test_handover_requires_other_driver_confirmation(self):
        op,other=self.trip()
        self.assertEqual(self.post('evento',{'id':str(uuid.uuid4()),'viaje':op.pk,'tipo':'INICIAR'}).status_code,200)
        self.assertEqual(self.post('evento',{'id':str(uuid.uuid4()),'viaje':op.pk,'tipo':'SOLICITAR_RELEVO','relevo':other.pk}).status_code,200)
        op.refresh_from_db();self.assertEqual(op.conduciendo_id,self.p.pk)
        self.assertEqual(self.post('evento',{'id':str(uuid.uuid4()),'viaje':op.pk,'tipo':'ACEPTAR_RELEVO'}).status_code,409)
        Sesion.objects.create(perfil=other,token_hash=hash_token('other-token'),vence=self.now+timedelta(days=1))
        self.auth={'HTTP_AUTHORIZATION':'Bearer other-token'}
        self.assertEqual(self.post('evento',{'id':str(uuid.uuid4()),'viaje':op.pk,'tipo':'ACEPTAR_RELEVO'}).status_code,200)
        op.refresh_from_db();self.assertEqual(op.conduciendo_id,other.pk)

    def test_existing_file_is_not_reimported(self):
        import base64,hashlib
        self.user.rol='BOLETERIA';self.user.save()
        self.trip()
        lote=Importacion.objects.get();lote.huella=hashlib.sha256(b'excel').hexdigest();lote.save()
        self.assertTrue(self.post('importar_itinerario',{'nombre':'igual.xlsx','contenido':base64.b64encode(b'excel').decode()}).json()['repetido'])
        self.assertEqual(Importacion.objects.count(),1)

    def test_inactive_user_token_rejected(self):
        self.user.esta_activo=False;self.user.save()
        self.assertEqual(self.post('inicio').status_code,401)

    def test_web_panel_requires_manager_and_renders(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/movil/').status_code,403)
        self.user.rol='CONTADORA';self.user.save()
        response=self.client.get('/movil/')
        self.assertContains(response,'Zonas de trabajo y pruebas')
        self.assertContains(response,'Solicitudes pendientes')
        self.assertContains(response,'csrfmiddlewaretoken')

    def test_web_activation_revokes_old_sessions(self):
        self.user.rol='CONTADORA';self.user.save();self.client.force_login(self.user)
        response=self.client.post('/movil/',{'accion':'habilitar','trabajador':self.worker.pk})
        self.assertContains(response,'Activación:')
        self.p.refresh_from_db();self.assertFalse(self.p.activado)
        self.assertFalse(Sesion.objects.get(token_hash=hash_token('token')).activa)

    def test_habilitar_creates_access_from_existing_worker_without_duplicate(self):
        self.user.rol='CONTADORA';self.user.save();self.client.force_login(self.user)
        ficha=Trabajador.objects.create(nombre_completo='ROSA PEREZ PRUEBA',dni='22222222',area='CONTABILIDAD',sede='CHICLAYO')
        before=Trabajador.objects.count()
        response=self.client.post('/movil/',{'accion':'habilitar','trabajador':ficha.pk})
        ficha.refresh_from_db()
        self.assertIsNotNone(ficha.usuario_id,response.content.decode()[-2000:])
        self.assertEqual(Trabajador.objects.count(),before)
        self.assertFalse(ficha.usuario.is_staff)
        self.assertFalse(ficha.usuario.is_superuser)
        self.assertEqual(ficha.usuario.rol,'ADMINISTRATIVO')
        self.assertFalse(ficha.usuario.has_usable_password())
        perfil=Perfil.objects.get(trabajador=ficha)
        self.assertTrue(perfil.activacion_hash)
        codigo=perfil.codigo
        self.client.post('/movil/',{'accion':'habilitar','trabajador':ficha.pk})
        self.assertEqual(get_user_model().objects.filter(dni=ficha.dni).count(),1)
        perfil.refresh_from_db();self.assertEqual(perfil.codigo,codigo)

    def test_new_driver_access_keeps_driver_link(self):
        self.user.rol='CONTADORA';self.user.save();self.client.force_login(self.user)
        ficha=Trabajador.objects.create(nombre_completo='JUAN PEREZ PRUEBA',dni='33333333',area='CONDUCTORES',sede='CHICLAYO')
        conductor=Conductor.objects.create(nombre=ficha.nombre_completo,trabajador=ficha)
        self.client.post('/movil/',{'accion':'habilitar','trabajador':ficha.pk})
        perfil=Perfil.objects.get(trabajador=ficha)
        self.assertEqual(perfil.conductor_id,conductor.pk)
        self.assertEqual(perfil.usuario.rol,'CONDUCTOR')

    def test_habilitar_does_not_reactivate_disabled_account(self):
        self.user.rol='CONTADORA';self.user.save();self.client.force_login(self.user)
        otro=get_user_model().objects.create_user(username='inactivo',email='x@example.invalid',dni='44444444',is_active=False)
        ficha=Trabajador.objects.get(usuario=otro)
        response=self.client.post('/movil/',{'accion':'habilitar','trabajador':ficha.pk})
        self.assertContains(response,'desactivada')
        self.assertFalse(Perfil.objects.filter(usuario=otro).exists())

    def activation_data(self):
        from .activacion import nuevo_codigo
        self.p.activado=False;self.p.dispositivo=''
        code=nuevo_codigo(self.p)
        self.p.activacion_hash=make_password(code);self.p.activacion_hasta=timezone.now()+timedelta(hours=24);self.p.save()
        return {'activacion':code,'dispositivo':'nuevo-device-123'}

    def test_activation_popup_then_password_then_separate_login(self):
        data=self.activation_data()
        response=self.post('verificar_activacion',data,False)
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['codigo'],self.p.codigo)
        self.assertNotIn('token',response.json())
        ticket=response.json()['ticket']
        password={'ticket':ticket,'password':'NuevaClaveSegura2026!','confirmacion':'NuevaClaveSegura2026!','dispositivo':data['dispositivo']}
        response=self.post('establecer_password',password,False)
        self.assertEqual(response.status_code,200,response.content)
        self.assertNotIn('token',response.json())
        self.assertFalse(Sesion.objects.filter(perfil=self.p,activa=True).exists())
        self.assertEqual(self.post('establecer_password',password,False).status_code,401)
        response=self.post('login',{'codigo':self.p.codigo,'password':password['password'],'dispositivo':data['dispositivo']},False)
        self.assertEqual(response.status_code,200)

    def test_activation_rate_limit_and_wrong_code(self):
        data=self.activation_data();data['activacion']+='incorrecto'
        for _ in range(8):self.assertEqual(self.post('verificar_activacion',data,False).status_code,401)
        self.assertEqual(self.post('verificar_activacion',data,False).status_code,429)

    def test_activation_proof_bound_to_device_and_current_code(self):
        data=self.activation_data()
        proof=self.post('verificar_activacion',data,False).json()['ticket']
        d={'ticket':proof,'password':'NuevaClaveSegura2026!','confirmacion':'NuevaClaveSegura2026!','dispositivo':'otro-device-123'}
        self.assertEqual(self.post('establecer_password',d,False).status_code,403)
        d['dispositivo']=data['dispositivo'];d['confirmacion']='diferente'
        self.assertEqual(self.post('establecer_password',d,False).status_code,400)
        self.activation_data()
        d['confirmacion']=d['password']
        self.assertEqual(self.post('establecer_password',d,False).status_code,401)

    def test_staff_home_has_attendance_not_driver_finances(self):
        from asistencia.models import ResumenAsistenciaDiaria
        self.p.conductor=None;self.p.save()
        self.user.rol='ADMINISTRATIVO';self.user.save()
        ResumenAsistenciaDiaria.objects.create(trabajador=self.worker,fecha=self.now.date(),horas_trabajadas=8,horas_nocturnas=2)
        response=self.post('inicio').json()
        self.assertFalse(response['perfil']['es_conductor'])
        self.assertFalse(response['perfil']['puede_ver_viajes'])
        self.assertEqual(response['viajes'],[])
        self.assertEqual(response['resumen']['jornadas'],1)
        self.assertEqual(Decimal(response['resumen']['horas_trabajadas']),8)
        for key in ['vueltas','trayectos_realizados','estimado','pagado','HORA','X','XX']:
            self.assertNotIn(key,response['resumen'])

    def test_driver_home_keeps_rounds_and_operations(self):
        response=self.post('inicio').json()
        self.assertTrue(response['perfil']['es_conductor'])
        self.assertTrue(response['perfil']['puede_ver_viajes'])
        self.assertIn('vueltas',response['resumen'])

    def test_sales_can_manage_trips_without_driver_pay_summary(self):
        self.p.conductor=None;self.p.save()
        self.user.rol='BOLETERIA';self.user.save()
        response=self.post('inicio').json()
        self.assertTrue(response['perfil']['puede_ver_viajes'])
        self.assertFalse(response['perfil']['es_conductor'])
        self.assertNotIn('vueltas',response['resumen'])

    def test_access_table_shows_area_and_temporary_code_inside_table(self):
        self.user.rol='CONTADORA';self.user.save();self.client.force_login(self.user)
        response=self.client.post('/movil/',{'accion':'habilitar','trabajador':self.worker.pk})
        self.assertContains(response,'<th>Área</th>',html=True)
        self.assertNotContains(response,'<th>Rol</th>',html=True)
        self.assertContains(response,'Conductores')
        code=response.context['activacion_codigo']
        body=response.content.decode()
        self.assertLess(body.index('<table'),body.index(code))
        self.assertGreater(body.index('</table>',body.index(code)),body.index(code))
        self.assertNotContains(self.client.get('/movil/'),code)
        self.assertIn('no-store',response.headers['Cache-Control'])

    def test_access_status_changes_only_after_creating_password(self):
        gestor=get_user_model().objects.create_user(username='gestor_estados',email='g@example.invalid',dni='55555555',rol='CONTADORA')
        self.client.force_login(gestor)
        data=self.activation_data()
        def status():
            result=self.client.get('/movil/accesos/estados/').json()
            return next(p['estado'] for p in result['perfiles'] if p['id']==self.p.pk)
        self.assertEqual(status(),'Pendiente')
        verified=self.post('verificar_activacion',data,False).json()
        self.assertEqual(status(),'Pendiente')
        response=self.post('establecer_password',{'ticket':verified['ticket'],'dispositivo':data['dispositivo'],'password':'NuevaClaveSegura2026!','confirmacion':'NuevaClaveSegura2026!'},False)
        self.assertEqual(response.status_code,200)
        self.assertEqual(status(),'Activado')
        self.assertNotIn(data['activacion'],self.client.get('/movil/accesos/estados/').content.decode())

    def test_access_status_endpoint_is_restricted(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/movil/accesos/estados/').status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get('/movil/accesos/estados/').status_code,302)

    def test_search_combines_people_and_deduplicates_linked_driver(self):
        self.user.rol='CONTADORA';self.user.save();self.client.force_login(self.user)
        Trabajador.objects.create(nombre_completo='PEREZ PERSONAL',dni='66666666',area='VENTAS',sede='CHICLAYO')
        Conductor.objects.create(nombre='PEREZ CONDUCTOR')
        response=self.client.get('/movil/personas/sugerencias/',{'q':'perez'}).json()['resultados']
        self.assertTrue(any(p['tipo']=='Trabajador' for p in response))
        self.assertTrue(any(p['tipo']=='Conductor' for p in response))
        linked=[p for p in response if p['id'] in [f'trabajador:{self.worker.pk}',f'conductor:{self.driver.pk}']]
        self.assertEqual(len(linked),1)
        self.assertEqual(linked[0]['id'],f'conductor:{self.driver.pk}')
        self.assertEqual(self.client.get('/movil/personas/sugerencias/',{'q':''}).json()['resultados'],[])
        for n in range(12):Conductor.objects.create(nombre=f'PEREZ CONDUCTOR {n}')
        self.assertLessEqual(len(self.client.get('/movil/personas/sugerencias/',{'q':'p'}).json()['resultados']),8)

    def test_driver_activation_stays_out_of_personal_catalog(self):
        self.user.rol='CONTADORA';self.user.save();self.client.force_login(self.user)
        driver=Conductor.objects.create(nombre='CONDUCTOR NUEVO PRUEBA')
        count=Trabajador.objects.count()
        response=self.client.post('/movil/',{'accion':'habilitar','persona':f'conductor:{driver.pk}','dni_conductor':'77777777','sede_conductor':'CAJAMARCA'})
        self.assertContains(response,'Activación:')
        p=Perfil.objects.get(conductor=driver)
        self.assertIsNone(p.trabajador_id)
        self.assertEqual(Trabajador.objects.count(),count)
        verified=self.post('verificar_activacion',{'activacion':response.context['activacion_codigo'],'dispositivo':'nuevo-device-conductor'},False).json()
        r=self.post('establecer_password',{'ticket':verified['ticket'],'dispositivo':'nuevo-device-conductor','password':'NuevaClaveSegura2026!','confirmacion':'NuevaClaveSegura2026!'},False)
        self.assertEqual(r.status_code,200)
        self.assertEqual(Trabajador.objects.count(),count)

    def test_search_requires_permissions_and_explicit_selection(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/movil/personas/sugerencias/',{'q':'a'}).status_code,403)
        self.user.rol='CONTADORA';self.user.save()
        response=self.client.post('/movil/',{'accion':'habilitar','persona':'otro:123'})
        self.assertContains(response,'Seleccione una sugerencia válida.')

    def test_drivers_can_activate_without_dni_or_site(self):
        self.user.rol='CONTADORA';self.user.save();self.client.force_login(self.user)
        count=Trabajador.objects.count()
        for i in range(2):
            driver=Conductor.objects.create(nombre=f'CONDUCTOR SIN DOCUMENTO {i}')
            response=self.client.post('/movil/',{'accion':'habilitar','persona':f'conductor:{driver.pk}'})
            self.assertContains(response,'Activación:')
            p=Perfil.objects.get(conductor=driver)
            self.assertIsNone(p.usuario.dni)
            self.assertEqual(p.usuario.agencia_sede,'')
        self.assertEqual(Trabajador.objects.count(),count)

    def test_individual_test_zone_only_authorizes_selected_profile(self):
        self.p.conductor=None;self.p.save()
        self.user.rol='CONTADORA';self.user.save();self.client.force_login(self.user)
        r=self.client.post('/movil/',{'accion':'zona','alcance':'trabajador','perfil':self.p.pk,'nombre':'Prueba personal','latitud':'-6.77','longitud':'-79.84','radio':'100'})
        self.assertEqual(r.status_code,200)
        zone=Zona.objects.get(nombre='Prueba personal')
        self.assertEqual(list(zone.perfiles.all()),[self.p])
        self.assertEqual(zone.sede,self.worker.sede)

    def test_sales_page_and_embarkation_assignment(self):
        op,_=self.trip()
        u=get_user_model().objects.create_user(username='embarcador',email='e@example.invalid',dni='88888888',rol='OPERADOR_EMBARQUE')
        perfil=Perfil.objects.create(usuario=u,trabajador=Trabajador.objects.get(usuario=u),activado=True)
        self.user.rol='BOLETERIA';self.user.save();self.client.force_login(self.user)
        self.assertContains(self.client.get('/movil/ventas/',{'viaje':op.pk}),'Responsable de embarque')
        r=self.post('asignar_embarque',{'viaje':op.pk,'perfil':perfil.pk,'conductores':True})
        self.assertEqual(r.status_code,200,r.content)
        self.assertTrue(op.embarcadores.filter(pk=perfil.pk).exists())
        op.refresh_from_db();self.assertTrue(op.permite_embarque_conductor)
        self.user.rol='ADMINISTRATIVO';self.user.save()
        self.assertEqual(self.post('asignar_embarque',{'viaje':op.pk,'perfil':perfil.pk}).status_code,403)

    def test_mobile_mark_review_only_from_daily_attendance(self):
        self.user.rol='CONTADORA';self.user.save()
        self.assertEqual(self.post('revisar_marca',{}).status_code,403)

    def test_offline_mark_can_be_confirmed_in_its_own_daily_detail(self):
        from asistencia.models import ResumenAsistenciaDiaria
        d=self.mark();d['offline']=True
        self.assertEqual(self.post('marcar',d).status_code,200)
        registro=Registro.objects.get(pk=d['id'])
        resumen=ResumenAsistenciaDiaria.objects.get(trabajador=self.worker,fecha=registro.jornada)
        gestor=get_user_model().objects.create_user(username='revision_diaria',email='r@example.invalid',dni='99999999',rol='CONTADORA')
        self.client.force_login(gestor)
        response=self.client.post(f'/movil/asistencia/{resumen.pk}/marca/',{'registro':str(registro.pk),'decision':'aceptar','fecha_confirmada':self.now.strftime('%Y-%m-%dT%H:%M'),'motivo':'Hora comprobada con el responsable'})
        self.assertEqual(response.status_code,302)
        registro.refresh_from_db()
        self.assertEqual(registro.estado,'REGISTRADO')
        self.assertIsNotNone(registro.marca_id)

    def test_profile_suggestions_for_commissions_and_sales(self):
        self.user.rol='CONTADORA';self.user.save();self.client.force_login(self.user)
        self.assertEqual(self.client.get('/movil/personas/sugerencias/',{'q':'ANA','scope':'personal'}).json()['resultados'],[])
        self.p.conductor=None;self.p.save()
        response=self.client.get('/movil/personas/sugerencias/',{'q':'ANA','scope':'personal'}).json()['resultados']
        self.assertEqual(response[0]['id'],str(self.p.pk))

    def test_real_excel_distributes_without_counting_programmed_trips(self):
        from io import BytesIO
        from tempfile import TemporaryDirectory
        from django.core.files.storage import FileSystemStorage
        from openpyxl import Workbook
        from zoneinfo import ZoneInfo
        import base64
        self.user.rol='BOLETERIA';self.user.save()
        other=Conductor.objects.create(nombre='JUAN TORRES PRUEBA')
        workbook=Workbook();sheet=workbook.active
        sheet.append(['FECHA','HORA','BUS','ORIGEN','DESTINO','CONDUCTOR 1','CONDUCTOR 2','CAPACIDAD','VEND 1ER PISO','VEND 2DO PISO'])
        local=self.now.astimezone(ZoneInfo('America/Lima'))
        sheet.append([local.strftime('%Y/%m/%d'),local.strftime('%H:%M'),'BUS1','Chiclayo','Cajamarca',self.driver.nombre,other.nombre,60,10,20])
        stream=BytesIO();workbook.save(stream)
        d={'nombre':'itinerario.xlsx','contenido':base64.b64encode(stream.getvalue()).decode()}
        field=Importacion._meta.get_field('archivo')
        with TemporaryDirectory() as directory, patch.object(field,'storage',FileSystemStorage(location=directory)):
            response=self.post('importar_itinerario',d)
            self.assertEqual(response.status_code,200,response.content)
            self.assertEqual(self.post('importar_itinerario',d).status_code,200)
        self.assertEqual(Operacion.objects.count(),1)
        op=Operacion.objects.get()
        self.assertEqual(op.salida.conductor_uno_id,self.driver.pk)
        self.assertEqual(op.salida.pasajes_vendidos,30)
        self.assertFalse(op.salida.cuenta_para_control)


