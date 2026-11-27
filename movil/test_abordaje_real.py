import uuid
from datetime import timedelta
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from . import tests as base_api
from .models import Pasajero, Perfil, Sesion, Auditoria
from .views import hash_token
from django.utils import timezone


@override_settings(SISMOC_DESCANSO_PUBLICACION_HABILITADA=False)
class AbordajeRealTests(TestCase):
    setUp = base_api.AppTests.setUp
    trip = base_api.AppTests.trip
    post = base_api.AppTests.post

    def preparar(self):
        op, otro = self.trip()
        p = Pasajero.objects.create(
            operacion=op, referencia='B-REAL-01', nombre='PASAJERO DE PRUEBA',
            documento='00123456', piso=1, asiento=1, origen='Chiclayo',
            destino='Cajamarca', punto='Paradero intermedio',
            punto_desembarque='Terminal de llegada')
        op.distribucion_asientos = {'piso1': 12, 'piso2': 48,
                                    'numeracion': 'continua', 'confirmada': True}
        op.save(update_fields=['distribucion_asientos'])
        return op, p, otro

    def cambiar(self, op, p, **cambios):
        return self.post('embarcar', {
            'id': str(uuid.uuid4()), 'viaje': op.pk, 'pasajero': p.pk,
            'anterior': 'PENDIENTE', 'estado': 'EMBARCADO',
            'identidad_verificada': True, **cambios})

    def test_conductor_asignado_ve_panel_y_detalle_sin_bandera_adicional(self):
        op, p, _ = self.preparar()
        self.assertFalse(op.permite_embarque_conductor)
        response = self.post('panel_abordaje')
        self.assertEqual(response.status_code, 200, response.content)
        viaje = response.json()['viajes'][0]
        self.assertEqual((viaje['id'], viaje['registrados'], viaje['capacidad']),
                         (op.pk, 1, 60))
        response = self.post('abordaje', {'viaje': op.pk})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data['puede_modificar'])
        self.assertEqual(data['pasajeros'][0]['punto'], p.punto)
        self.assertEqual(data['viaje']['conductores'][0]['dni'], self.user.dni)
        self.assertEqual(data['empresa']['ruc'], '')
        self.assertEqual(Pasajero.objects.get(pk=p.pk).estado, 'PENDIENTE')
        self.assertFalse(Auditoria.objects.filter(accion='embarque').exists())

    def test_embarcador_solo_ve_y_modifica_su_operacion_asignada(self):
        op, p, _ = self.preparar()
        usuario = get_user_model().objects.create_user(
            username='embarcador.real', dni=None, rol='OPERADOR_EMBARQUE')
        perfil = Perfil.objects.create(usuario=usuario, activado=True)
        Sesion.objects.create(perfil=perfil, token_hash=hash_token('operario-token'),
                              vence=timezone.now() + timedelta(days=1))
        self.auth = {'HTTP_AUTHORIZATION': 'Bearer operario-token'}
        self.assertEqual(self.post('panel_abordaje').json()['viajes'], [])
        self.assertEqual(self.post('abordaje', {'viaje': op.pk}).status_code, 403)
        self.assertEqual(self.cambiar(op, p).status_code, 403)
        op.embarcadores.add(perfil)
        self.assertEqual(self.post('panel_abordaje').json()['viajes'][0]['id'], op.pk)
        self.assertEqual(self.cambiar(op, p).status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.verificado_por_id, perfil.pk)

    def test_conductor_ajeno_no_accede_a_detalles_ni_modifica(self):
        op, p, _ = self.preparar()
        self.p.conductor = None
        self.p.save(update_fields=['conductor'])
        self.assertEqual(self.post('abordaje', {'viaje': op.pk}).status_code, 403)
        self.assertEqual(self.cambiar(op, p).status_code, 403)

    def test_panel_acepta_mes_y_devuelve_viaje_del_mes(self):
        op, otro = self.trip()
        mes = timezone.localdate().strftime('%Y-%m')
        respuesta = self.post('panel_abordaje', {'mes': mes})
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        datos = respuesta.json()
        self.assertEqual(datos['mes'], mes)
        self.assertIn(op.pk, [v['id'] for v in datos['viajes']])

    def test_cambio_exige_identidad_conflicto_e_idempotencia(self):
        op, p, _ = self.preparar()
        self.assertEqual(self.cambiar(op, p, identidad_verificada=False).status_code, 400)
        eid = str(uuid.uuid4())
        self.assertEqual(self.cambiar(op, p, id=eid).status_code, 200)
        self.assertEqual(self.cambiar(op, p, id=eid).status_code, 200)
        self.assertEqual(self.cambiar(op, p).status_code, 409)
        self.assertEqual(Auditoria.objects.filter(accion='embarque').count(), 1)
        self.assertEqual(self.cambiar(op, p, anterior='EMBARCADO').status_code, 409)
        self.assertEqual(self.cambiar(op, p, anterior='EMBARCADO',
                                     estado='DESEMBARCADO').status_code, 200)

    def test_viaje_en_curso_admite_recojo_y_cerrado_no(self):
        op, p, _ = self.preparar()
        op.estado = 'EN_CURSO'
        op.save(update_fields=['estado'])
        op.salida.fecha = timezone.localdate() - timedelta(days=1)
        op.salida.save(update_fields=['fecha'])
        self.assertEqual(self.cambiar(op, p).status_code, 200)
        op.estado = 'FINALIZADO'
        op.save(update_fields=['estado'])
        response = self.post('abordaje', {'viaje': op.pk})
        self.assertFalse(response.json()['puede_modificar'])
        self.assertEqual(self.cambiar(op, p, anterior='EMBARCADO',
                                     estado='DESEMBARCADO').status_code, 409)

    def test_cancelado_no_se_puede_modificar(self):
        op, p, _ = self.preparar()
        op.salida.anulado = True
        op.salida.save(update_fields=['anulado'])
        self.assertEqual(self.post('panel_abordaje').json()['viajes'], [])
        self.assertEqual(self.cambiar(op, p).status_code, 409)
