from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from . import test_itinerarios_compartidos as base
from django.test import TestCase
from .models import Auditoria,Operacion,Pasajero
from .models import Perfil
from django.utils import timezone
from datetime import timedelta
from conductores.models import Salida,Conductor
from .programacion_manual import programar


class BusesEmbarqueTests(TestCase):
    setUp=base.ItinerariosCompartidosTests.setUp

    def abrir(self):
        return self.client.post('/movil/buses/',{'accion':'abrir','salida':self.s.pk,'desde':'2026-08-01','hasta':'2026-08-01'},follow=True)

    def configurar(self):
        self.abrir()
        return self.client.post('/movil/buses/',{'accion':'distribucion','salida':self.s.pk,'piso1':12,'piso2':48,'numeracion':'continua'},follow=True)

    def archivo(self,asiento=13,nombre='ANA PRUEBA'):
        wb=Workbook();ws=wb.active
        ws.append(['Boleto','Pasajero','Documento','Piso','Asiento','Origen','Destino','Punto de embarque','Punto de desembarque'])
        ws.append(['B001',nombre,'00123456',2,asiento,'Chiclayo','Cajamarca','Cruce Mochumí','Terminal Cajamarca'])
        b=BytesIO();wb.save(b);return SimpleUploadedFile('pasajeros.xlsx',b.getvalue())

    def subir(self,archivo=None):
        return self.client.post('/movil/buses/',{'accion':'pasajeros_excel','salida':self.s.pk,'archivo':archivo or self.archivo()},follow=True)

    def test_fechas_por_defecto_cubren_el_mes_actual(self):
        hoy=timezone.localdate()
        desde=hoy.replace(day=1)
        hasta=(desde.replace(year=desde.year+1,month=1)
               if desde.month==12 else desde.replace(month=desde.month+1))-timedelta(days=1)
        respuesta=self.client.get('/movil/buses/')
        self.assertEqual(respuesta.context['desde'],desde)
        self.assertEqual(respuesta.context['hasta'],hasta)
        self.assertContains(respuesta,'value="%s"' % desde.isoformat())
        self.assertContains(respuesta,'value="%s"' % hasta.isoformat())
        self.assertContains(respuesta,'Mes actual')

    def test_viajes_reales_filtrados_y_popup_sin_duplicados(self):
        self.assertContains(self.client.get('/movil/buses/?desde=2026-08-01&hasta=2026-08-01'),'BUS1')
        response=self.client.get('/movil/buses/?desde=2026-08-02&hasta=2026-08-02')
        self.assertNotIn('BUS1',[s.bus for s in response.context['viajes_buses']])
        self.assertContains(self.abrir(),'data-bus-dialog')
        self.abrir();self.assertEqual(Operacion.objects.count(),1)
        self.assertEqual(self.s.__class__.objects.count(),1)

    def test_distribucion_y_excel_rellenan_asientos_y_puntos(self):
        self.configurar()
        response=self.subir()
        self.assertContains(response,'Cruce Mochumí')
        self.assertContains(response,'Terminal Cajamarca')
        p=Pasajero.objects.get();self.assertEqual((p.piso,p.asiento),(2,13));self.assertEqual(p.documento,'00123456')
        self.assertContains(response,f'data-open-seat="asiento-{p.pk}"')

    def test_distribucion_debe_confirmarse_y_respetar_capacidad(self):
        self.abrir();self.subir();self.assertFalse(Pasajero.objects.exists())
        self.client.post('/movil/buses/',{'accion':'distribucion','salida':self.s.pk,'piso1':10,'piso2':48,'numeracion':'continua'})
        self.assertFalse(Operacion.objects.get().distribucion_asientos)

    def test_reimportacion_conserva_embarque_y_rechaza_cambios_verificados(self):
        self.configurar();self.subir()
        p=Pasajero.objects.get();p.estado='EMBARCADO';p.save()
        self.subir();self.assertEqual(Pasajero.objects.count(),1)
        self.subir(self.archivo(nombre='OTRA PERSONA'))
        p.refresh_from_db();self.assertEqual(p.nombre,'ANA PRUEBA');self.assertEqual(p.estado,'EMBARCADO')

    def test_asiento_inexistente_no_importa(self):
        self.configurar();self.subir(self.archivo(asiento=99));self.assertFalse(Pasajero.objects.exists())

    def test_editar_puntos_y_plantilla_excel(self):
        self.configurar();self.subir();p=Pasajero.objects.get()
        self.client.post('/movil/buses/',{'accion':'puntos','salida':self.s.pk,'pasajero':p.pk,'punto':'Paradero intermedio','punto_desembarque':'Cruce de llegada'})
        p.refresh_from_db();self.assertEqual(p.punto_desembarque,'Cruce de llegada')
        self.assertEqual(self.client.get('/movil/buses/?plantilla=1')['Content-Type'],'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_contadora_no_accede_a_buses(self):
        self.u.rol='CONTADORA';self.u.save(update_fields=['rol'])
        self.assertEqual(self.client.get('/movil/buses/').status_code,403)

    def test_programar_selecciona_placa_y_publica_solo_con_cuentas_vinculadas(self):
        self.assertContains(self.client.get('/movil/buses/'), 'data-programar-abrir')
        self.assertContains(self.client.get('/movil/buses/'), 'name="conductor_uno"')
        placas=self.client.get('/movil/buses/sugerencias/?tipo=placa&q=BUS1').json()['resultados']
        self.assertTrue(any(o.get('id')=='BUS1' for o in placas))
        from django.contrib.auth import get_user_model
        for i, conductor in enumerate((self.c1, self.c2)):
            usuario=get_user_model().objects.create_user(username=f'conductor_{i}',rol='CONDUCTOR')
            Perfil.objects.create(usuario=usuario,conductor=conductor,activo=True)
        fecha=timezone.localdate()+timedelta(days=2)
        datos={'accion':'programar','fecha':str(fecha),'hora':'08:30','origen':'Chiclayo',
               'destino':'Jaén','bus':'BUS1','conductor_uno':self.c1.pk,'conductor_dos':self.c2.pk}
        placas=self.client.get('/movil/buses/sugerencias/?tipo=placa&q=BUS1').json()['resultados']
        sedes=self.client.get('/movil/buses/sugerencias/?tipo=sede&q=CHIC').json()['resultados']
        self.assertTrue(any(o.get('id')=='BUS1' for o in placas))
        response=self.client.post('/movil/buses/',datos,follow=True)
        self.assertEqual(response.status_code,200,response.content)
        salida=Salida.objects.get(fecha=fecha)
        self.assertEqual(salida.original['origen_programacion'],'MANUAL')
        self.assertEqual((salida.conductor_uno_id,salida.conductor_dos_id),(self.c1.pk,self.c2.pk))
        self.assertEqual(Operacion.objects.filter(salida=salida).count(),1)
        self.assertTrue(salida.original.get('publicacion_descanso_autorizada',False))
        from .views import datos_viaje
        detalle=datos_viaje(Operacion.objects.get(salida=salida),Perfil.objects.get(conductor=self.c1),{
            'embarques':set(),'perfiles':{},'incidencias':{},'puntos':{},
        })
        self.assertTrue(detalle['asignado'])
        self.assertTrue(detalle['programacion_manual'])
        self.assertFalse(detalle['reporte_validado'])
        self.assertEqual(detalle['bus'],'BUS1')
        from .descanso_publicacion import estado_publicacion, EvaluadorPublicacionLote
        op=Operacion.objects.get(salida=salida)
        self.assertTrue(estado_publicacion(op)[0])
        self.assertTrue(EvaluadorPublicacionLote([op],None).estado(op)[0])
        self.assertEqual(self.client.post('/movil/buses/',datos).status_code,302)
        self.assertEqual(Salida.objects.filter(fecha=fecha).count(),1)
        self.assertEqual(self.s.bus,'BUS1')

    def test_editar_viaje_conserva_pasajeros_y_distribucion(self):
        fecha = timezone.localdate()+timedelta(days=2)
        datos = {'accion':'programar','fecha':str(fecha),'hora':'08:30','origen':'Chiclayo',
                 'destino':'Cajamarca','bus':'BUS1','conductor_uno':self.c1.pk,
                 'conductor_dos':self.c2.pk}
        self.client.post('/movil/buses/', datos)
        salida = Salida.objects.get(fecha=fecha)
        op = Operacion.objects.get(salida=salida)
        self.client.post('/movil/buses/', {'accion':'distribucion','salida':salida.pk,
                         'piso1':12,'piso2':48,'numeracion':'continua'})
        self.client.post('/movil/buses/', {'accion':'pasajeros_excel','salida':salida.pk,
                         'archivo':self.archivo()})
        pasajero = Pasajero.objects.get(operacion=op)
        op.refresh_from_db()
        config = op.distribucion_asientos
        self.assertContains(self.client.get(
            f'/movil/buses/?desde={fecha}&hasta={fecha}&salida={salida.pk}'), 'data-editar-abrir')
        edicion = {**datos, 'accion':'editar', 'salida':salida.pk, 'hora':'09:45'}
        response = self.client.post('/movil/buses/', edicion, follow=True)
        self.assertEqual(response.status_code, 200, response.content)
        salida.refresh_from_db(); op.refresh_from_db(); pasajero.refresh_from_db()
        self.assertEqual(salida.hora.strftime('%H:%M'), '09:45')
        self.assertEqual(op.distribucion_asientos, config)
        self.assertEqual(Pasajero.objects.count(), 1)
        self.assertEqual(pasajero.asiento, 13)
        self.assertContains(response, 'data-editar-abrir')
        self.assertTrue(Auditoria.objects.filter(accion='editar_viaje_manual').exists())

    def test_sugerencias_embarcador_y_boton_en_popup(self):
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.create_user(
            username='encargado.sugerencia', email='enc@example.invalid',
            dni='99999999', rol='OPERADOR_EMBARQUE')
        perfil = Perfil.objects.create(usuario=u, activado=True)
        self.u.rol = 'BOLETERIA'
        self.u.save(update_fields=['rol'])
        self.client.force_login(self.u)
        sugerencias = self.client.get(
            '/movil/buses/sugerencias/', {'tipo': 'embarcador', 'q': 'encargado'})
        self.assertEqual(sugerencias.status_code, 200)
        self.assertTrue(any(o['id'] == str(perfil.pk)
                            for o in sugerencias.json()['resultados']))
        Operacion.objects.get_or_create(salida=self.s)
        respuesta = self.client.get('/movil/buses/', {
            'desde': str(self.s.fecha), 'hasta': str(self.s.fecha),
            'salida': self.s.pk})
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn('data-embarcador-abrir', html)
        self.assertIn('Responsable de embarque', html)
        self.assertNotIn('<select name="perfil"', html)

    def test_programar_rechaza_placa_ajena_y_conductor_repetido(self):
        fecha=str(timezone.localdate()+timedelta(days=2))
        datos={'fecha':fecha,'hora':'08:30','origen':'Chiclayo','destino':'Jaén',
               'bus':'BUS-OTRO','conductor_uno':self.c1.pk,'conductor_dos':self.c2.pk}
        from .views import Problema
        with self.assertRaises(Problema):
            programar(datos,self.u)
        datos['bus']='BUS1';datos['conductor_dos']=self.c1.pk
        with self.assertRaises(Problema):
            programar(datos,self.u)
        self.assertEqual(Salida.objects.count(),1)

    def test_sin_viaje_el_dia_anterior_publica_sin_alta_inicial(self):
        from django.contrib.auth import get_user_model
        from django.test import override_settings
        from .models import ReglaDescanso
        for i, conductor in enumerate((self.c1, self.c2)):
            usuario=get_user_model().objects.create_user(username=f'prueba_descanso_{i}',rol='CONDUCTOR')
            Perfil.objects.create(usuario=usuario,conductor=conductor,activo=True)
        ReglaDescanso.objects.create(activa=True,horas=8)
        fecha=timezone.localdate()+timedelta(days=2)
        datos={'fecha':str(fecha),'hora':'08:30','origen':'Chiclayo','destino':'Jaén',
               'bus':'BUS1','conductor_uno':self.c1.pk,'conductor_dos':self.c2.pk}
        with override_settings(SISMOC_DESCANSO_PUBLICACION_HABILITADA=True):
            op,publicada,motivo=programar(datos,self.u)
            self.assertTrue(publicada,motivo)
            from .descanso_publicacion import estado_publicacion
            self.assertTrue(estado_publicacion(op)[0])
        self.assertEqual(Operacion.objects.count(),1)
        previa=Salida.objects.create(importacion=self.lote,fila=9,
            fecha=fecha-timedelta(days=1),hora='08:30',bus='BUS PREVIO',
            origen='Chiclayo',destino='Jaén',conductor_uno=self.c1,
            conductor_dos=self.c2,nombre_uno='UNO PRUEBA',nombre_dos='DOS PRUEBA',clave='d'*64)
        Operacion.objects.create(salida=previa)
        from .programacion_manual import comprobar_descanso
        publicada,motivo=comprobar_descanso(op)
        self.assertFalse(publicada)
        self.assertIn('Sin llegada real',motivo)

    def test_programacion_autorizada_aparece_solo_a_sus_conductores(self):
        from django.contrib.auth import get_user_model
        from .models import AutorizacionInicialDescanso
        from .views import snapshot
        perfiles=[]
        for i, conductor in enumerate((self.c1,self.c2)):
            usuario=get_user_model().objects.create_user(username=f'conductor_publicado_{i}',rol='CONDUCTOR')
            perfil=Perfil.objects.create(usuario=usuario,conductor=conductor,activo=True)
            AutorizacionInicialDescanso.objects.create(
                perfil=perfil,autorizado_por=self.u,motivo='Alta inicial de prueba')
            perfiles.append(perfil)
        fecha=timezone.localdate()+timedelta(days=2)
        op,publicada,_=programar({
            'fecha':str(fecha),'hora':'08:30','origen':'Chiclayo',
            'destino':'Jaén','bus':'BUS1','conductor_uno':self.c1.pk,
            'conductor_dos':self.c2.pk,
        },self.u)
        self.assertTrue(publicada)
        self.assertTrue(op.salida.original['publicacion_descanso_autorizada'])
        for perfil in perfiles:
            viaje=next(v for v in snapshot(perfil)['viajes'] if v['id']==op.pk)
            self.assertTrue(viaje['asignado'])
            self.assertTrue(viaje['programacion_manual'])
            self.assertFalse(viaje['reporte_validado'])
        op.salida.hora=op.salida.hora.replace(hour=9)
        op.salida.save(update_fields=['hora'])
        from .descanso_publicacion import estado_publicacion
        self.assertFalse(estado_publicacion(op)[0])
        for perfil in perfiles:
            self.assertNotIn(op.pk,[v['id'] for v in snapshot(perfil)['viajes']])
        ajeno=Conductor.objects.create(nombre='TERCERO PRUEBA')
        usuario=get_user_model().objects.create_user(username='conductor_ajeno',rol='CONDUCTOR')
        perfil_ajeno=Perfil.objects.create(usuario=usuario,conductor=ajeno,activo=True)
        self.assertNotIn(op.pk,[v['id'] for v in snapshot(perfil_ajeno)['viajes']])

    def test_solo_control_publica_pendiente_tras_altas_auditadas(self):
        from django.contrib.auth import get_user_model
        from .models import AutorizacionInicialDescanso,Auditoria
        from .programacion_manual import publicar_pendiente
        from .views import Problema
        perfiles=[]
        for i, conductor in enumerate((self.c1,self.c2)):
            usuario=get_user_model().objects.create_user(username=f'pendiente_{i}',rol='CONDUCTOR')
            perfiles.append(Perfil.objects.create(usuario=usuario,conductor=conductor,activo=True))
        fecha=timezone.localdate()+timedelta(days=2)
        previa=Salida.objects.create(importacion=self.lote,fila=8,
            fecha=fecha-timedelta(days=1),hora='08:30',bus='BUS PREVIO',
            origen='Chiclayo',destino='Jaén',conductor_uno=self.c1,
            conductor_dos=self.c2,nombre_uno='UNO PRUEBA',nombre_dos='DOS PRUEBA',clave='c'*64)
        Operacion.objects.create(salida=previa)
        op,publicada,_=programar({
            'fecha':str(fecha),'hora':'08:30','origen':'Chiclayo',
            'destino':'Jaén','bus':'BUS1','conductor_uno':self.c1.pk,
            'conductor_dos':self.c2.pk,
        },self.u)
        self.assertFalse(publicada)
        with self.assertRaises(Problema):
            publicar_pendiente(op.salida_id,self.u)
        self.u.rol='ADMINISTRADOR';self.u.save(update_fields=['rol'])
        with self.assertRaises(Problema):
            publicar_pendiente(op.salida_id,self.u)
        from datetime import datetime, time
        alta_el = timezone.make_aware(
            datetime.combine(fecha-timedelta(days=1),time(9)),
            timezone.get_default_timezone())
        for perfil in perfiles:
            AutorizacionInicialDescanso.objects.create(
                perfil=perfil,autorizado_por=self.u,
                motivo='Alta inicial para prueba',autorizado_el=alta_el)
        publicar_pendiente(op.salida_id,self.u)
        op.salida.refresh_from_db()
        self.assertTrue(op.salida.original['publicacion_descanso_autorizada'])
        self.assertTrue(Auditoria.objects.filter(accion='publicar_programacion_manual').exists())

    def test_excel_con_datos_distintos_compara_con_programacion_sin_reemplazarla(self):
        from django.contrib.auth import get_user_model
        from .comparacion_itinerarios import comparar_filas
        for i, conductor in enumerate((self.c1,self.c2)):
            usuario=get_user_model().objects.create_user(username=f'comparacion_{i}',rol='CONDUCTOR')
            Perfil.objects.create(usuario=usuario,conductor=conductor,activo=True)
        fecha=timezone.localdate()+timedelta(days=2)
        op,_,_=programar({
            'fecha':str(fecha),'hora':'08:30','origen':'Chiclayo',
            'destino':'Jaén','bus':'BUS1','conductor_uno':self.c1.pk,
            'conductor_dos':self.c2.pk,
        },self.u)
        propuesta={
            'fila':3,'fecha':fecha,'hora':op.salida.hora,'bus':'BUS-OTRO',
            'origen':op.salida.origen,'destino':op.salida.destino,
            'nombre_uno':self.c1.nombre,'nombre_dos':self.c2.nombre,
            'anulado':False,'clave':'c'*64,'original':{'comercial':{}},
        }
        diferencia=comparar_filas([propuesta])[0]
        self.assertEqual(diferencia['estado'],'CAMBIO')
        self.assertEqual(diferencia['salida_id'],op.salida_id)
        self.assertIn('Bus',{d['campo'] for d in diferencia['diferencias']})
        op.salida.refresh_from_db()
        self.assertEqual(op.salida.bus,'BUS1')


from . import tests as base_api


class BusesApiTests(TestCase):
    setUp=base_api.AppTests.setUp
    trip=base_api.AppTests.trip
    post=base_api.AppTests.post

    def test_conductor_asignado_consulta_y_modifica_embarque(self):
        import uuid
        op,_=self.trip()
        Pasajero.objects.create(operacion=op,referencia='B001',nombre='ANA PRUEBA',documento='00123456',piso=1,asiento=1,origen='Chiclayo',destino='Cajamarca',punto='Paradero intermedio',punto_desembarque='Cruce de llegada')
        response=self.post('pasajeros',{'viaje':op.pk})
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['pasajeros'][0]['punto_desembarque'],'Cruce de llegada')
        pasajero=Pasajero.objects.get(operacion=op)
        response=self.post('embarcar',{'viaje':op.pk,'id':str(uuid.uuid4()),
            'pasajero':pasajero.pk,'anterior':'PENDIENTE','estado':'EMBARCADO',
            'identidad_verificada':True})
        self.assertEqual(response.status_code,200,response.content)
        self.p.conductor=None;self.p.save()
        self.assertEqual(self.post('pasajeros',{'viaje':op.pk}).status_code,403)
