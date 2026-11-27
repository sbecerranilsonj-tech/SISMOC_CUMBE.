from datetime import datetime, timedelta
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from conductores.models import Conductor, Importacion, Salida
from conductores.services import confirmar, calendario
from .descanso_publicacion import estado_publicacion, EvaluadorPublicacionLote
from .models import (AutorizacionInicialDescanso, Descanso, Operacion,
                     Perfil, ReglaDescanso, Sesion, Auditoria)
from .views import hash_token


@override_settings(SISMOC_DESCANSO_PUBLICACION_HABILITADA=True)
class PublicacionDescansoTests(TestCase):
    def setUp(self):
        self.now = timezone.localtime(timezone.now())
        self.revisor = get_user_model().objects.create_user(
            username='control_descanso', email='control@example.invalid',
            dni='91800101', password='prueba', rol='CONTADORA',
        )
        self.perfiles = []
        for numero in range(2):
            usuario = get_user_model().objects.create_user(
                username=f'chofer_{numero}', email=f'chofer{numero}@example.invalid',
                dni=f'9180010{numero + 2}', password='prueba', rol='CONDUCTOR',
            )
            conductor = Conductor.objects.create(nombre=f'CHOFER PRUEBA {numero}')
            self.perfiles.append(Perfil.objects.create(
                usuario=usuario, conductor=conductor, activado=True,
            ))
        fecha = (self.now + timedelta(days=2)).date()
        self.lote = Importacion.objects.create(
            nombre='descanso.xls', huella='f' * 64, inicio=fecha, fin=fecha,
            creado_por=self.revisor,
        )
        self.salida = Salida.objects.create(
            importacion=self.lote, fila=1, fecha=fecha, hora=self.now.time(),
            bus='BUS DESCANSO', origen='Chiclayo', destino='Cajamarca',
            conductor_uno=self.perfiles[0].conductor,
            conductor_dos=self.perfiles[1].conductor,
            nombre_uno='CHOFER PRUEBA 0', nombre_dos='CHOFER PRUEBA 1',
            clave='a' * 64,
        )
        ReglaDescanso.objects.create(activa=True, horas=8)

    def test_reporte_pendiente_no_se_publica_y_validacion_vincula_operacion(self):
        op = Operacion.objects.create(salida=self.salida)
        self.assertFalse(estado_publicacion(op)[0])
        self.assertIn('Reporte sin validar', estado_publicacion(op)[1])
        self.lote.estado = 'VALIDADO'
        self.lote.save(update_fields=['estado'])
        self.assertTrue(estado_publicacion(op)[0])

    def test_viaje_antiguo_sin_llegada_no_bloquea_al_dia_siguiente(self):
        self.lote.estado = 'VALIDADO'
        self.lote.save(update_fields=['estado'])
        antigua = Salida.objects.create(
            importacion=self.lote, fila=5,
            fecha=self.salida.fecha - timedelta(days=5), hora=self.salida.hora,
            bus='BUS ANTIGUO', origen='Chiclayo', destino='Cajamarca',
            conductor_uno=self.perfiles[0].conductor,
            conductor_dos=self.perfiles[1].conductor,
            clave='e' * 64,
        )
        Operacion.objects.create(salida=antigua)
        op = Operacion.objects.create(salida=self.salida)
        self.assertTrue(estado_publicacion(op)[0])

    def test_viaje_el_dia_anterior_sin_llegada_si_bloquea(self):
        self.lote.estado = 'VALIDADO'
        self.lote.save(update_fields=['estado'])
        previa = Salida.objects.create(
            importacion=self.lote, fila=6,
            fecha=self.salida.fecha - timedelta(days=1), hora=self.salida.hora,
            bus='BUS PREVIO', origen='Chiclayo', destino='Cajamarca',
            conductor_uno=self.perfiles[0].conductor,
            conductor_dos=self.perfiles[1].conductor,
            clave='d' * 64,
        )
        Operacion.objects.create(salida=previa)
        op = Operacion.objects.create(salida=self.salida)
        self.assertIn('Sin llegada real', estado_publicacion(op)[1])

    def test_validacion_web_muestra_el_viaje_sin_historial_previo(self):
        confirmar(self.lote.pk, self.revisor)
        op = Operacion.objects.get(salida=self.salida)
        Sesion.objects.create(
            perfil=self.perfiles[0], token_hash=hash_token('token-descanso'),
            vence=timezone.now() + timedelta(days=1),
        )
        def rutas():
            return self.client.post(
                '/movil/api/rutas_periodo/',
                data=json.dumps({'mes': self.salida.fecha.strftime('%Y-%m')}),
                content_type='application/json',
                HTTP_AUTHORIZATION='Bearer token-descanso',
            ).json()['viajes']
        self.assertEqual([viaje['id'] for viaje in rutas()], [op.pk])

    def test_alta_inicial_solo_control_con_motivo_y_auditoria(self):
        url = '/conductores/control/descanso-inicial/'
        datos = {'perfil': self.perfiles[0].pk,
                 'motivo': 'Se verificó el descanso previo con la empresa.'}
        self.assertEqual(self.client.post(url, datos).status_code, 302)
        self.assertFalse(AutorizacionInicialDescanso.objects.exists())
        self.client.force_login(self.perfiles[0].usuario)
        self.assertEqual(self.client.post(url, datos).status_code, 403)
        self.client.force_login(self.revisor)
        self.assertEqual(self.client.post(url, datos).status_code, 302)
        self.assertEqual(AutorizacionInicialDescanso.objects.count(), 1)
        self.assertEqual(Auditoria.objects.filter(
            accion='autorizar_descanso_inicial',
        ).count(), 1)
        self.assertEqual(self.client.post(url, datos).status_code, 302)
        self.assertEqual(AutorizacionInicialDescanso.objects.count(), 1)

    def test_segundo_viaje_sigue_exigiendo_llegada_y_descanso(self):
        self.lote.estado = 'VALIDADO'
        self.lote.save(update_fields=['estado'])
        op = Operacion.objects.create(salida=self.salida)
        self.assertTrue(estado_publicacion(op)[0])
        siguiente = Salida.objects.create(
            importacion=self.lote, fila=2,
            fecha=self.salida.fecha + timedelta(days=1),
            hora=self.salida.hora, bus='BUS REGRESO',
            origen='Cajamarca', destino='Chiclayo',
            conductor_uno=self.perfiles[0].conductor,
            conductor_dos=self.perfiles[1].conductor,
            clave='b' * 64,
        )
        regreso = Operacion.objects.create(salida=siguiente)
        self.assertIn('Sin llegada real', estado_publicacion(regreso)[1])
        op.estado = 'FINALIZADO'
        op.llegada_real = timezone.make_aware(
            datetime.combine(self.salida.fecha, self.salida.hora),
            timezone.get_default_timezone(),
        ) + timedelta(hours=4)
        op.save(update_fields=['estado', 'llegada_real'])
        for perfil in self.perfiles:
            Descanso.objects.create(
                perfil=perfil, operacion=op,
                inicio=op.llegada_real + timedelta(minutes=5),
            )
        self.assertTrue(estado_publicacion(regreso)[0])
        op.llegada_real += timedelta(hours=21)
        op.save(update_fields=['llegada_real'])
        self.assertIn('Descanso insuficiente', estado_publicacion(regreso)[1])

    def test_calendario_grande_con_consultas_acotadas_y_mismos_motivos(self):
        self.lote.estado = 'VALIDADO'
        self.lote.save(update_fields=['estado'])
        operaciones = [Operacion.objects.create(salida=self.salida)]
        for numero in range(2, 82):
            salida = Salida.objects.create(
                importacion=self.lote, fila=numero,
                fecha=self.salida.fecha + timedelta(days=numero // 3),
                hora=self.salida.hora, bus=f'BUS {numero}',
                origen='Chiclayo', destino='Cajamarca',
                conductor_uno=self.perfiles[0].conductor,
                conductor_dos=self.perfiles[1].conductor,
                clave=f'{numero:064x}',
            )
            operaciones.append(Operacion.objects.create(salida=salida))
        with CaptureQueriesContext(connection) as consultas:
            _, filas = calendario(self.salida.fecha, operaciones[-1].salida.fecha)
        self.assertLessEqual(len(consultas), 12)
        motivos = {
            s.pk: s.motivo_publicacion
            for fila in filas for celda in fila['celdas']
            for s in celda['viajes'] + celda['excluidas']
        }
        for op in operaciones:
            self.assertEqual(
                motivos[op.salida_id], estado_publicacion(op)[1],
            )

    def test_evaluador_lote_coincide_con_descanso_y_alta_inicial(self):
        self.lote.estado = 'VALIDADO'
        self.lote.save(update_fields=['estado'])
        op = Operacion.objects.create(salida=self.salida)
        for perfil in self.perfiles:
            AutorizacionInicialDescanso.objects.create(
                perfil=perfil, autorizado_por=self.revisor,
                motivo='Descanso inicial confirmado por Control.',
            )
        siguiente = Salida.objects.create(
            importacion=self.lote, fila=2,
            fecha=self.salida.fecha + timedelta(days=1),
            hora=self.salida.hora, bus='BUS REGRESO',
            origen='Cajamarca', destino='Chiclayo',
            conductor_uno=self.perfiles[0].conductor,
            conductor_dos=self.perfiles[1].conductor,
            clave='b' * 64,
        )
        regreso = Operacion.objects.create(salida=siguiente)
        op.llegada_real = timezone.make_aware(
            datetime.combine(self.salida.fecha, self.salida.hora),
            timezone.get_default_timezone(),
        ) + timedelta(hours=4)
        op.save(update_fields=['llegada_real'])
        for perfil in self.perfiles:
            Descanso.objects.create(
                perfil=perfil, operacion=op,
                inicio=op.llegada_real + timedelta(minutes=5),
            )
        evaluador = EvaluadorPublicacionLote([op, regreso], ReglaDescanso.objects.get())
        for viaje in (op, regreso):
            self.assertEqual(evaluador.estado(viaje), estado_publicacion(viaje))
