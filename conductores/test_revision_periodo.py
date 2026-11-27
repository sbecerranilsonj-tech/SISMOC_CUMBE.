from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from core.models import Usuario
from .models import Auditoria, Conductor, Importacion, Salida


class RevisionPeriodoTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username='revisor_periodo', email='revisor@example.test',
            dni='95100999', password='prueba', rol='CONTADORA',
        )
        self.client.force_login(self.usuario)
        self.uno = Conductor.objects.create(nombre='UNO DE PRUEBA')
        self.dos = Conductor.objects.create(nombre='DOS DE PRUEBA')
        self.fecha = date(2026, 8, 7)
        self.lote = Importacion.objects.create(
            nombre='prueba.xls', huella='e' * 64, archivo='itinerarios/prueba.xls',
            inicio=self.fecha, fin=self.fecha, estado='VALIDADO',
            creado_por=self.usuario,
        )
        self.salida = Salida.objects.create(
            importacion=self.lote, fila=1, fecha=self.fecha, hora=time(15, 30),
            bus='PRUEBA', origen='Cajamarca', destino='Chiclayo',
            conductor_uno=self.uno, conductor_dos=self.dos,
            nombre_uno=self.uno.nombre, nombre_dos=self.dos.nombre,
            clave='e' * 64,
            original={'comercial': {'vendidos_primer_piso': 0, 'vendidos_segundo_piso': 0}},
        )
        self.url = reverse('conductores_revision_periodo')
        self.periodo = {'desde': '2026-08-07', 'hasta': '2026-08-07'}

    def test_consulta_no_modifica_y_confirmacion_cancela_una_vez_con_auditoria(self):
        preview = self.client.get(self.url, self.periodo).json()
        self.assertEqual(preview['faltantes'], [])
        self.assertEqual(preview['pendientes'], 1)  # Dos conductores, una sola salida.
        self.salida.refresh_from_db()
        self.assertEqual(self.salida.estado_operativo, 'AUTO')
        respuesta = self.client.post(self.url, {
            **self.periodo, 'comprobante': preview['comprobante'],
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['canceladas'], 1)
        self.salida.refresh_from_db()
        self.assertEqual(self.salida.estado_operativo, 'CANCELADO')
        self.assertEqual(self.salida.original['comercial']['vendidos_primer_piso'], 0)
        self.assertEqual(Auditoria.objects.filter(
            importacion=self.lote, mensaje__contains='Revisión global',
        ).count(), 1)
        self.assertEqual(self.client.post(self.url, {
            **self.periodo, 'comprobante': preview['comprobante'],
        }).status_code, 409)

    def test_dia_vacio_bloquea_y_muestra_trabajador_y_fecha(self):
        periodo = {'desde': '2026-08-07', 'hasta': '2026-08-08'}
        preview = self.client.get(self.url, periodo).json()
        self.assertEqual(len(preview['faltantes']), 2)
        self.assertEqual({f['fecha'] for f in preview['faltantes']}, {'2026-08-08'})
        self.assertFalse(preview['comprobante'])
        self.assertEqual(self.client.post(self.url, {
            **periodo, 'comprobante': '',
        }).status_code, 409)
        self.salida.refresh_from_db()
        self.assertEqual(self.salida.estado_operativo, 'AUTO')

    def test_cambio_tras_preview_impide_cancelacion(self):
        preview = self.client.get(self.url, self.periodo).json()
        self.salida.estado_operativo = 'REALIZADO'
        self.salida.save(update_fields=['estado_operativo'])
        self.assertEqual(self.client.post(self.url, {
            **self.periodo, 'comprobante': preview['comprobante'],
        }).status_code, 409)
        self.salida.refresh_from_db()
        self.assertEqual(self.salida.estado_operativo, 'REALIZADO')
