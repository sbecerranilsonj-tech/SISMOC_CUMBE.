import uuid
from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from conductores.models import Conductor, Importacion, Salida
from . import tests as base_api
from .models import Auditoria, Descanso, Operacion, Perfil, Sesion
from .programacion_manual import programar
from .views import hash_token


class DescansoAutomaticoTests(TestCase):
    setUp = base_api.AppTests.setUp
    post = base_api.AppTests.post

    def preparar(self, horas_desde_llegada):
        conductores = []
        perfiles = []
        for i in range(2):
            usuario = get_user_model().objects.create_user(
                username=f'descanso.auto.{i}', email=f'descanso{i}@example.invalid',
                dni=f'9000000{i}', rol='CONDUCTOR')
            conductor = Conductor.objects.create(nombre=f'CONDUCTOR DESCANSO {i}')
            perfil = Perfil.objects.create(
                usuario=usuario, conductor=conductor, activado=True)
            Sesion.objects.create(
                perfil=perfil, token_hash=hash_token(f'descanso-token-{i}'),
                vence=timezone.now() + timedelta(days=1))
            conductores.append(conductor)
            perfiles.append(perfil)
        lote = Importacion.objects.create(
            nombre='descanso automático', huella='d' * 64,
            inicio=timezone.localdate() - timedelta(days=1),
            fin=timezone.localdate(), estado='VALIDADO', creado_por=self.user)
        anterior = Salida.objects.create(
            importacion=lote, fila=1,
            fecha=timezone.localdate() - timedelta(days=1), hora=time(7),
            bus='BUS DESC', origen='Chiclayo', destino='Cajamarca',
            conductor_uno=conductores[0], conductor_dos=conductores[1],
            nombre_uno='UNO PRUEBA', nombre_dos='DOS PRUEBA', clave='f' * 64)
        previa = Operacion.objects.create(
            salida=anterior, estado='FINALIZADO',
            llegada_real=timezone.now() - timedelta(hours=horas_desde_llegada))
        hora = (timezone.localtime() + timedelta(hours=3)).strftime('%H:%M')
        datos = {'fecha': str(timezone.localdate()), 'hora': hora,
                 'origen': 'Chiclayo', 'destino': 'Jaen', 'bus': 'BUS DESC',
                 'conductor_uno': conductores[0].pk,
                 'conductor_dos': conductores[1].pk}
        self.auth = {'HTTP_AUTHORIZATION': 'Bearer descanso-token-0'}
        return previa, datos, perfiles

    def test_programar_bloquea_y_muestra_aviso_sin_8_horas(self):
        previa, datos, perfiles = self.preparar(2)
        op, publicada, motivo = programar(datos, self.user)
        self.assertFalse(publicada)
        self.assertIn('Descanso insuficiente', motivo)
        self.assertFalse(op.salida.original.get('publicacion_descanso_autorizada'))
        viaje = next(v for v in self.post('inicio').json()['viajes']
                     if v['id'] == op.pk)
        self.assertTrue(viaje['descanso_insuficiente'])
        self.assertIn('Descanso insuficiente', viaje['disponibilidad']['mensaje'])
        self.assertFalse(Auditoria.objects.filter(
            accion='publicar_descanso_automatico').exists())

    def test_control_no_aprueba_y_boleteria_publica_automaticamente(self):
        previa, datos, perfiles = self.preparar(2)
        op, publicada, _ = programar(datos, self.user)
        self.assertFalse(publicada)
        previa.llegada_real = timezone.now() - timedelta(hours=9)
        previa.save(update_fields=['llegada_real'])
        perfiles[0].usuario.rol = 'BOLETERIA'
        perfiles[0].usuario.save(update_fields=['rol'])
        respuesta = self.post('publicar_automatico', {'salida': op.salida_id})
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        op.salida.refresh_from_db()
        self.assertTrue(op.salida.original['publicacion_descanso_autorizada'])
        self.assertTrue(Auditoria.objects.filter(
            accion='publicar_descanso_automatico').exists())
        viaje = next(v for v in self.post('inicio').json()['viajes']
                     if v['id'] == op.pk)
        self.assertFalse(viaje['descanso_insuficiente'])
        self.assertTrue(viaje['disponibilidad']['permitido'])

    def test_tarjeta_web_se_muestra_roja_y_pide_cambiar_conductor(self):
        previa, datos, perfiles = self.preparar(2)
        op, publicada, _ = programar(datos, self.user)
        self.assertFalse(publicada)
        self.user.rol = 'BOLETERIA'
        self.user.save(update_fields=['rol'])
        self.client.force_login(self.user)
        fecha = str(timezone.localdate())
        respuesta = self.client.get('/movil/buses/',
                                    {'desde': fecha, 'hasta': fecha})
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn('bus-pendiente', html)
        self.assertIn('En espera de confirmar la llegada', html)
        self.assertIn('Comprobar conductores', html)
        self.assertIn('publicar_automatico', html)
        revisada = self.client.get('/movil/buses/',
                                   {'desde': fecha, 'hasta': fecha,
                                    'descanso_revisado': '1'})
        html_revisada = revisada.content.decode()
        self.assertIn('bus-descanso-rojo', html_revisada)
        self.assertIn('Cambie de conductor', html_revisada)

    def test_viaje_manual_finalizado_aparece_sin_publicacion_de_central(self):
        previa, datos, perfiles = self.preparar(2)
        op, publicada, _ = programar(datos, self.user)
        self.assertFalse(publicada)
        previa.llegada_real = timezone.now() - timedelta(hours=9)
        previa.save(update_fields=['llegada_real'])
        actual = timezone.localtime(timezone.now())
        op.salida.fecha = actual.date()
        op.salida.hora = actual.time()
        op.salida.save(update_fields=['fecha', 'hora'])
        self.assertEqual(self.post('evento', {'id': str(uuid.uuid4()),
            'viaje': op.pk, 'tipo': 'INICIAR'}).status_code, 200)
        op.refresh_from_db()
        op.salida_real = timezone.now() - timedelta(hours=8)
        op.save(update_fields=['salida_real'])
        self.assertEqual(self.post('evento', {'id': str(uuid.uuid4()),
            'viaje': op.pk, 'tipo': 'LLEGADA'}).status_code, 200)
        op.refresh_from_db()
        self.assertEqual(op.estado, 'FINALIZADO')
        self.assertFalse(op.salida.original.get('publicacion_descanso_autorizada'))
        self.assertIn(op.pk, [v['id'] for v in self.post('inicio').json()['viajes']])
        mes = timezone.localdate().strftime('%Y-%m')
        self.assertIn(op.pk, [v['id'] for v in self.post(
            'rutas_periodo', {'mes': mes}).json()['viajes']])

    def test_sin_llegada_se_publica_como_validacion_pendiente_en_app(self):
        previa, datos, perfiles = self.preparar(2)
        previa.llegada_real = None
        previa.save(update_fields=['llegada_real'])
        op, publicada, motivo = programar(datos, self.user)
        self.assertFalse(publicada)
        self.assertIn('Sin llegada real', motivo)
        viaje = next(v for v in self.post('inicio').json()['viajes']
                     if v['id'] == op.pk)
        self.assertTrue(viaje['validacion_pendiente'])
        self.assertIn('Sin llegada real', viaje['disponibilidad']['mensaje'])

    def test_panel_muestra_conductores_disponibles_y_no_disponibles(self):
        previa, datos, perfiles = self.preparar(2)
        programar(datos, self.user)
        self.user.rol = 'BOLETERIA'
        self.user.save(update_fields=['rol'])
        self.client.force_login(self.user)
        respuesta = self.client.get('/movil/buses/',
                                    {'desde': str(timezone.localdate()),
                                     'hasta': str(timezone.localdate())})
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn('Disponibilidad de conductores', html)
        self.assertIn('No disponible', html)
        self.assertIn('Sin llegada real', html)

    def test_llamada_directa_publicar_automatico(self):
        from .programacion_manual import publicar_automatico
        previa, datos, perfiles = self.preparar(2)
        op, publicada, _ = programar(datos, self.user)
        self.assertFalse(publicada)
        previa.llegada_real = timezone.now() - timedelta(hours=9)
        previa.save(update_fields=['llegada_real'])
        publicar_automatico(op.salida_id, perfiles[0].usuario)
        op.salida.refresh_from_db()
        self.assertTrue(op.salida.original['publicacion_descanso_autorizada'])

    def test_programar_publica_solo_con_la_llegada_real(self):
        previa, datos, perfiles = self.preparar(9)
        op, publicada, motivo = programar(datos, self.user)
        self.assertTrue(publicada, motivo)
        self.assertTrue(op.salida.original['publicacion_descanso_autorizada'])
        self.assertFalse(Descanso.objects.filter(
            perfil__in=perfiles).exists())
