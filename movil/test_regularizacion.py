import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from . import tests as base_api
from .models import Auditoria, EventoViaje, Operacion, Perfil, Sesion
from .views import hash_token


class RegularizacionLlegadaTests(TestCase):
    setUp = base_api.AppTests.setUp
    trip = base_api.AppTests.trip
    post = base_api.AppTests.post

    def viaje_en_curso(self):
        op, otro = self.trip()
        self.assertEqual(self.post('evento', {'id': str(uuid.uuid4()),
            'viaje': op.pk, 'tipo': 'INICIAR'}).status_code, 200)
        op.refresh_from_db()
        self.assertEqual(op.estado, 'EN_CURSO')
        op.salida_real = timezone.now() - timedelta(hours=9)
        op.save(update_fields=['salida_real'])
        return op, otro

    def datos(self, op, **cambios):
        datos = {'id': str(uuid.uuid4()), 'viaje': op.pk,
                 'llegada': (timezone.now() - timedelta(hours=1)).isoformat(),
                 'motivo': 'Llegué al destino y olvidé marcar la llegada en la app.'}
        datos.update(cambios)
        return datos

    def test_acepta_hora_sin_zona_y_formato_de_fecha_separado(self):
        op, otro = self.viaje_en_curso()
        naive = timezone.localtime(timezone.now() - timedelta(hours=1)).replace(
            tzinfo=None)
        respuesta = self.post('regularizar_llegada', self.datos(
            op, llegada=naive.isoformat()))
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        op.refresh_from_db()
        self.assertIsNotNone(op.llegada_real)

    def test_conductor_asignado_registra_llegada_tardia_con_auditoria(self):
        op, otro = self.viaje_en_curso()
        datos = self.datos(op)
        respuesta = self.post('regularizar_llegada', datos)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        op.refresh_from_db()
        self.assertEqual(op.estado, 'FINALIZADO')
        self.assertIsNotNone(op.llegada_real)
        self.assertIn(self.p, op.llegadas_confirmadas.all())
        self.assertEqual(EventoViaje.objects.filter(
            operacion=op, tipo='LLEGADA_TARDIA').count(), 1)
        self.assertTrue(Auditoria.objects.filter(
            accion='regularizar_llegada').exists())
        viaje = self.post('inicio').json()['viajes'][0]
        self.assertFalse(viaje['llegada_pendiente'])

    def test_registro_repetido_se_rechaza(self):
        op, otro = self.viaje_en_curso()
        datos = self.datos(op)
        self.assertEqual(self.post('regularizar_llegada', datos).status_code, 200)
        self.assertEqual(self.post('regularizar_llegada', datos).status_code, 409)

    def test_motivo_es_opcional(self):
        op, otro = self.viaje_en_curso()
        respuesta = self.post('regularizar_llegada', self.datos(op, motivo=''))
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        op.refresh_from_db()
        self.assertEqual(op.estado, 'FINALIZADO')

    def test_regularizacion_exige_siete_horas_de_trayecto(self):
        op, otro = self.viaje_en_curso()
        corto = (timezone.now() - timedelta(hours=7, minutes=30)).isoformat()
        respuesta = self.post('regularizar_llegada', self.datos(op, llegada=corto))
        self.assertEqual(respuesta.status_code, 422, respuesta.content)
        self.assertIn('7 horas', respuesta.json()['error'])

    def test_hora_fuera_de_rango_se_rechaza(self):
        op, otro = self.viaje_en_curso()
        futuro = (timezone.now() + timedelta(hours=1)).isoformat()
        self.assertEqual(self.post('regularizar_llegada',
                                   self.datos(op, llegada=futuro)).status_code, 422)
        anterior = (timezone.now() - timedelta(hours=7)).isoformat()
        self.assertEqual(self.post('regularizar_llegada',
                                   self.datos(op, llegada=anterior)).status_code, 422)

    def test_conductor_ajeno_no_puede(self):
        op, otro = self.viaje_en_curso()
        self.p.conductor = None
        self.p.save(update_fields=['conductor'])
        self.assertEqual(self.post('regularizar_llegada',
                                   self.datos(op)).status_code, 403)

    def test_ventas_puede_regularizar(self):
        op, otro = self.viaje_en_curso()
        self.user.rol = 'BOLETERIA'
        self.user.save(update_fields=['rol'])
        respuesta = self.post('regularizar_llegada', self.datos(op))
        self.assertEqual(respuesta.status_code, 200, respuesta.content)

    def test_no_se_puede_regularizar_viaje_ya_finalizado(self):
        op, otro = self.viaje_en_curso()
        self.post('regularizar_llegada', self.datos(op))
        self.assertEqual(self.post('regularizar_llegada',
                                   self.datos(op)).status_code, 409)
