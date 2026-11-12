from datetime import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from core.models import Usuario
from asistencia.models import Trabajador, IdentidadBiometrica, MarcacionBiometrica, CierreAsistencia, RevisionAsistencia


class FichasTrabajadorTests(TestCase):
    def test_editar_seleccionado_no_confirma_vinculo(self):
        ficha = Trabajador.objects.create(**self.datos, sede='CAJAMARCA')
        resultado = self.client.get(reverse('buscar_trabajadores'), {'q':'Jorge'}).json()['resultados'][0]
        self.assertEqual(resultado['url_editar'], reverse('editar_ficha_trabajador', args=[ficha.pk]))
        respuesta = self.client.post(resultado['url_editar'], {**self.datos, 'nombre_completo':'Jorge Aguilar Ramos'})
        self.assertEqual(respuesta.status_code, 200)
        ficha.refresh_from_db()
        self.identidad.refresh_from_db()
        self.assertEqual(ficha.nombre_completo, 'Jorge Aguilar Ramos')
        self.assertIsNone(self.identidad.trabajador_id)

    def setUp(self):
        self.admin = Usuario.objects.create_user('gestor_fichas', email='gestor@example.invalid', dni='12345678', rol='CONTADORA', first_name='Ana', last_name='Pérez')
        self.identidad = IdentidadBiometrica.objects.create(sede='CAJAMARCA', equipo='1', codigo='13', nombre='PASAPERA')
        self.client.force_login(self.admin)
        self.registro = reverse('registrar_trabajador', args=[self.identidad.pk])
        self.confirmacion = reverse('confirmar_trabajador', args=[self.identidad.pk])
        self.datos = {'nombre_completo': 'Jorge Aguilar', 'dni': '87654321', 'area': 'Administración'}

    def test_guardar_y_vincular_no_crea_cuenta(self):
        res = self.client.post(self.registro, self.datos)
        self.assertEqual(res.status_code, 201)
        ficha = Trabajador.objects.get(dni='87654321')
        self.identidad.refresh_from_db()
        self.assertEqual(self.identidad.trabajador, ficha)
        self.assertEqual(ficha.sede, 'CAJAMARCA')
        self.assertIsNone(ficha.usuario_id)
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(ficha.codigo, '13')
        self.assertTrue(RevisionAsistencia.objects.filter(accion='Ficha de trabajador vinculada').exists())

    def test_busqueda_por_nombre_dni_codigo_y_codigo_huellero(self):
        self.client.post(self.registro, self.datos)
        ficha = Trabajador.objects.get(dni='87654321')
        for consulta in ['Jorge Aguilar', 'aguil', '87654321', ficha.codigo, '13']:
            res = self.client.get(reverse('buscar_trabajadores'), {'q': consulta})
            self.assertIn(ficha.pk, [t['id'] for t in res.json()['resultados']])

    def test_codigo_importado_repetido_en_otro_equipo_no_confunde_fichas(self):
        self.client.post(self.registro, self.datos)
        otra = IdentidadBiometrica.objects.create(sede='TRUJILLO', equipo='2', codigo='13')
        res = self.client.post(reverse('registrar_trabajador', args=[otra.pk]), {**self.datos, 'nombre_completo': 'Pedro Morales', 'dni': '87654322', 'codigo': 'CODIGO-MANIPULADO'})
        self.assertEqual(res.status_code, 201)
        otra.refresh_from_db()
        self.assertEqual(otra.trabajador.codigo, '13')
        self.assertNotEqual(otra.trabajador_id, Trabajador.objects.get(dni='87654321').pk)
        self.assertEqual(len(self.client.get(reverse('buscar_trabajadores'), {'q': '13'}).json()['resultados']), 2)

    def test_cuenta_existente_tiene_ficha_buscable(self):
        res = self.client.get(reverse('buscar_trabajadores'), {'q': 'Pérez'})
        self.assertEqual(res.json()['resultados'][0]['dni'], self.admin.dni)
        ficha = self.admin.ficha_trabajador
        self.assertEqual(self.client.post(self.confirmacion, {'trabajador': ficha.pk}).status_code, 200)

    def test_duplicado_y_dni_invalido_no_crean_fichas(self):
        self.assertEqual(self.client.post(self.registro, {**self.datos, 'dni': '2'}).status_code, 400)
        self.assertEqual(self.client.post(self.registro, {**self.datos, 'dni': self.admin.dni}).status_code, 400)
        self.assertEqual(Trabajador.objects.count(), 1)

    def test_no_reasignar_ni_dejar_ficha_huerfana_por_error(self):
        self.client.post(self.registro, self.datos)
        res = self.client.post(self.registro, {**self.datos, 'dni': '87654322'})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Trabajador.objects.filter(dni='87654322').exists())
        res = self.client.post(self.confirmacion, {'trabajador': self.admin.ficha_trabajador.pk})
        self.assertEqual(res.status_code, 400)

    def test_identificacion_respeta_periodo_cerrado(self):
        fecha = timezone.make_aware(datetime(2026, 8, 1, 8))
        MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad, fecha_hora=fecha)
        CierreAsistencia.objects.create(fecha_inicio=fecha.date(), fecha_fin=fecha.date(), total_jornadas=0)
        res = self.client.post(self.registro, self.datos)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Trabajador.objects.filter(dni='87654321').exists())

    def test_permisos_y_csrf(self):
        seguro = Client(enforce_csrf_checks=True)
        seguro.force_login(self.admin)
        self.assertEqual(seguro.post(self.registro, self.datos).status_code, 403)
        empleado = Usuario.objects.create_user('solo_personal', email='personal@example.invalid', dni='11111111', rol='ADMINISTRATIVO')
        self.client.force_login(empleado)
        self.assertEqual(self.client.post(self.registro, self.datos).status_code, 403)
        self.assertEqual(self.client.post(self.confirmacion, {'trabajador': self.admin.ficha_trabajador.pk}).status_code, 403)
        self.assertEqual(self.client.get(reverse('buscar_trabajadores'), {'q': 'Ana'}).status_code, 403)

    def test_editar_ficha_actualiza_identificacion_sin_cambiar_codigo(self):
        self.client.post(self.registro, self.datos)
        res = self.client.post(reverse('editar_trabajador', args=[self.identidad.pk]), {**self.datos, 'nombre_completo': 'Jorge Aguilar Ramos', 'dni': '87654322', 'area': 'Boletería', 'codigo': '99'})
        self.assertEqual(res.status_code, 200)
        self.identidad.refresh_from_db()
        self.assertEqual(self.identidad.nombre, 'Jorge Aguilar Ramos')
        self.assertEqual(self.identidad.codigo, '13')
        self.assertEqual(self.identidad.trabajador.dni, '87654322')
        self.assertEqual(self.identidad.trabajador.area, 'Boletería')
        self.assertTrue(RevisionAsistencia.objects.filter(accion='Ficha de trabajador editada').exists())
        res = self.client.get(reverse('dashboard'), {'vista': 'excel-zk'})
        self.assertContains(res, 'Editar trabajador')
        self.assertContains(res, 'Jorge Aguilar Ramos')

    def test_edicion_rechaza_documento_duplicado(self):
        self.client.post(self.registro, self.datos)
        res = self.client.post(reverse('editar_trabajador', args=[self.identidad.pk]), {**self.datos, 'dni': self.admin.dni})
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.json()['conflicto']['destino']['dni'], self.admin.dni)
        self.assertEqual(Trabajador.objects.get(identidades=self.identidad).dni, self.datos['dni'])

    def test_corregir_dni_existente_unifica_solo_con_confirmacion(self):
        self.client.post(self.registro, self.datos)
        origen = Trabajador.objects.get(dni=self.datos['dni'])
        destino = self.admin.ficha_trabajador
        fecha = timezone.make_aware(datetime(2026, 8, 1, 8))
        marca = MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad, fecha_hora=fecha)
        otra = IdentidadBiometrica.objects.create(sede='CAJAMARCA', equipo='2', codigo='13', trabajador=origen)
        url = reverse('editar_trabajador', args=[self.identidad.pk])
        res = self.client.post(url, {**self.datos, 'dni': destino.dni})
        self.assertEqual(res.status_code, 409)
        self.assertTrue(Trabajador.objects.filter(pk=origen.pk).exists())
        res = self.client.post(url, {**self.datos, 'dni': destino.dni, 'usar_existente': '1', 'destino_id': destino.pk, 'origen_id': origen.pk})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Trabajador.objects.filter(pk=origen.pk).exists())
        for identidad in [self.identidad, otra]:
            identidad.refresh_from_db()
            self.assertEqual(identidad.trabajador_id, destino.pk)
            self.assertEqual(identidad.codigo, '13')
        marca.refresh_from_db()
        self.assertEqual(marca.fecha_hora, fecha)
        self.assertEqual(marca.identidad_biometrica_id, self.identidad.pk)
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertTrue(RevisionAsistencia.objects.filter(accion='Ficha duplicada corregida').exists())

    def test_unificacion_no_modifica_periodo_cerrado(self):
        self.client.post(self.registro, self.datos)
        origen = Trabajador.objects.get(dni=self.datos['dni'])
        fecha = timezone.make_aware(datetime(2026, 8, 1, 8))
        MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad, fecha_hora=fecha)
        CierreAsistencia.objects.create(fecha_inicio=fecha.date(), fecha_fin=fecha.date(), total_jornadas=0)
        res = self.client.post(reverse('editar_trabajador', args=[self.identidad.pk]), {**self.datos, 'dni': self.admin.dni, 'usar_existente': '1', 'destino_id': self.admin.ficha_trabajador.pk, 'origen_id': origen.pk})
        self.assertEqual(res.status_code, 400)
        self.identidad.refresh_from_db()
        self.assertEqual(self.identidad.trabajador_id, origen.pk)
        self.assertTrue(Trabajador.objects.filter(pk=origen.pk).exists())

    def test_filtros_de_codigos_combinan_sede_codigo_y_nombre(self):
        self.client.post(self.registro, self.datos)
        IdentidadBiometrica.objects.create(sede='TRUJILLO', equipo='1', codigo='13', nombre='Jorge Aguilar')
        IdentidadBiometrica.objects.create(sede='CAJAMARCA', equipo='1', codigo='15', nombre='Pedro Morales')
        filtros = {'vista': 'excel-zk', 'sede_codigo': 'CAJAMARCA', 'filtro_codigo': '13', 'nombre_codigo': 'aguil'}
        respuesta = self.client.get(reverse('dashboard'), filtros)
        self.assertEqual([i.pk for i in respuesta.context['identidades_biometricas']], [self.identidad.pk])
        self.assertEqual(respuesta.context['total_codigos_filtrados'], 1)
        self.assertContains(respuesta, 'Nombre del trabajador')
        self.assertContains(respuesta, 'nombre_codigo=aguil')
        respuesta = self.client.get(reverse('dashboard'), {**filtros, 'nombre_codigo': 'inexistente'})
        self.assertEqual(respuesta.context['total_codigos_filtrados'], 0)
        self.assertContains(respuesta, 'No se encontraron registros.')

    def test_edicion_respeta_cierre_y_permisos(self):
        self.client.post(self.registro, self.datos)
        url = reverse('editar_trabajador', args=[self.identidad.pk])
        seguro = Client(enforce_csrf_checks=True)
        seguro.force_login(self.admin)
        self.assertEqual(seguro.post(url, self.datos).status_code, 403)
        fecha = timezone.make_aware(datetime(2026, 8, 1, 8))
        MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad, fecha_hora=fecha)
        CierreAsistencia.objects.create(fecha_inicio=fecha.date(), fecha_fin=fecha.date(), total_jornadas=0)
        self.assertEqual(self.client.post(url, {**self.datos, 'area': 'Ventas'}).status_code, 400)
        self.assertEqual(Trabajador.objects.get(identidades=self.identidad).area, self.datos['area'])
        self.admin.rol = 'ADMINISTRATIVO'
        self.admin.save()
        self.assertEqual(self.client.post(url, self.datos).status_code, 403)
