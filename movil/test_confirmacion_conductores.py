import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from . import tests as base_api
from .models import Perfil, Sesion
from .views import hash_token


class ConfirmacionConductoresTests(TestCase):
    setUp = base_api.AppTests.setUp
    trip = base_api.AppTests.trip
    post = base_api.AppTests.post

    def otro_conductor(self, op):
        perfil = Perfil.objects.get(conductor=op.salida.conductor_dos)
        Sesion.objects.create(
            perfil=perfil, token_hash=hash_token('companero-token'),
            vence=timezone.now() + timedelta(days=1))
        return perfil

    def evento(self, tipo):
        return self.post('evento', {'id': str(uuid.uuid4()), 'viaje': self.op.pk,
                                    'tipo': tipo})

    def test_una_confirmacion_inicia_y_llegada_es_compartida(self):
        self.op, otro = self.trip()
        companero = self.otro_conductor(self.op)
        self.assertEqual(self.evento('LLEGADA').status_code, 409)
        self.assertEqual(self.evento('INICIAR').status_code, 200)
        self.op.refresh_from_db()
        self.assertEqual(self.op.estado, 'EN_CURSO')
        self.assertIsNotNone(self.op.salida_real)
        self.assertIsNone(self.op.llegada_real)
        datos = self.post('inicio').json()['viajes'][0]
        self.assertTrue(datos['confirmado'])
        self.assertEqual(datos['confirmaciones'], 1)
        self.assertEqual(self.evento('INICIAR').status_code, 409)
        self.auth = {'HTTP_AUTHORIZATION': 'Bearer companero-token'}
        ajeno = self.post('inicio').json()['viajes'][0]
        self.assertEqual(ajeno['estado'], 'EN_CURSO')
        self.assertEqual(ajeno['salida_real'], datos['salida_real'])
        self.assertFalse(ajeno['confirmado'])
        self.op.refresh_from_db()
        self.op.salida_real = timezone.now() - timedelta(hours=8)
        self.op.save(update_fields=['salida_real'])
        self.assertEqual(self.evento('LLEGADA').status_code, 200)
        self.op.refresh_from_db()
        self.assertEqual(self.op.estado, 'FINALIZADO')
        self.assertIsNotNone(self.op.llegada_real)
        self.assertEqual(self.evento('LLEGADA').status_code, 409)
        self.auth = {'HTTP_AUTHORIZATION': 'Bearer token'}
        propio = self.post('inicio').json()['viajes'][0]
        self.assertEqual(propio['llegada_real'],
                         self.post('inicio').json()['viajes'][0]['llegada_real'])

    def test_inicio_solo_dentro_de_la_hora_programada(self):
        self.op, otro = self.trip()
        futuro = timezone.localtime(timezone.now()) + timedelta(hours=2)
        self.op.salida.fecha = futuro.date()
        self.op.salida.hora = futuro.time()
        self.op.salida.save(update_fields=['fecha', 'hora'])
        respuesta = self.evento('INICIAR')
        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertIn('hora programada', respuesta.json()['error'])
        otro_momento = timezone.localtime(timezone.now()) + timedelta(hours=1)
        self.op.salida.fecha = otro_momento.date()
        self.op.salida.hora = otro_momento.time()
        self.op.salida.save(update_fields=['fecha', 'hora'])
        self.assertEqual(self.evento('INICIAR').status_code, 409)
        actual = timezone.localtime(timezone.now())
        self.op.salida.fecha = actual.date()
        self.op.salida.hora = actual.time()
        self.op.salida.save(update_fields=['fecha', 'hora'])
        self.assertEqual(self.evento('INICIAR').status_code, 200)

    def test_llegada_requiere_siete_horas_de_viaje(self):
        self.op, otro = self.trip()
        self.otro_conductor(self.op)
        self.assertEqual(self.evento('INICIAR').status_code, 200)
        respuesta = self.evento('LLEGADA')
        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertIn('7 horas', respuesta.json()['error'])
        self.op.refresh_from_db()
        self.op.salida_real = timezone.now() - timedelta(hours=7, minutes=1)
        self.op.save(update_fields=['salida_real'])
        self.assertEqual(self.evento('LLEGADA').status_code, 200)

    def test_sin_companero_activo_no_puede_iniciar(self):
        self.op, otro = self.trip()
        otro.activo = False
        otro.save(update_fields=['activo'])
        otro.usuario.save(update_fields=['esta_activo'])
        self.assertEqual(self.evento('INICIAR').status_code, 409)
        self.op.refresh_from_db()
        self.assertEqual(self.op.estado, 'PROGRAMADO')
        self.assertEqual(self.op.confirmado_por.count(), 0)
