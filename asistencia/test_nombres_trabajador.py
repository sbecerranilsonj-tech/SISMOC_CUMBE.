from django.test import TestCase
from django.urls import reverse

from asistencia.forms import TrabajadorForm
from asistencia.models import Trabajador, IdentidadBiometrica
from core.models import Usuario


class NombresTrabajadorTests(TestCase):
    def setUp(self):
        self.actor = Usuario.objects.create_user(username="nombres_admin", email="nombres@example.invalid", dni="12345678", rol="CONTADORA")
        self.client.force_login(self.actor)
        self.identidad = IdentidadBiometrica.objects.create(sede="Chiclayo", codigo="13", nombre="SILUPU")
        self.datos = dict(nombres=" Nilson  Jesús ", apellido_paterno="Silupu", apellido_materno="Becerra", dni="87654321", area="Administración")

    def test_registrar_buscar_editar_y_mostrar_sin_perder_nombre_completo(self):
        respuesta = self.client.post(reverse("registrar_trabajador", args=[self.identidad.pk]), self.datos)
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.json()["trabajador"]["nombre"], "Silupu Nilson")
        ficha = Trabajador.objects.get(dni=self.datos["dni"])
        self.assertEqual(ficha.nombre_completo, "Nilson Jesús Silupu Becerra")
        resultado = self.client.get(reverse("buscar_trabajadores"), {"q": "Jesús Becerra"}).json()["resultados"][0]
        self.assertEqual(resultado["nombre"], "Silupu Nilson")
        self.assertEqual(resultado["apellido_materno"], "Becerra")
        self.assertEqual(resultado["nombre_completo"], ficha.nombre_completo)
        pagina = self.client.get(reverse("dashboard"), {"vista": "excel-zk"})
        self.assertContains(pagina, "Silupu Nilson")
        self.assertContains(pagina, 'data-apellido-materno="Becerra"')
        respuesta = self.client.post(resultado["url_editar"], {**self.datos, "nombres": "Jesús Nilson", "apellido_paterno": "De la Cruz"})
        self.assertEqual(respuesta.status_code, 200)
        ficha.refresh_from_db()
        self.identidad.refresh_from_db()
        self.assertEqual(ficha.nombre_corto, "De la Cruz Jesús")
        self.assertEqual(self.identidad.nombre, "Jesús Nilson De la Cruz Becerra")
        self.assertEqual(self.identidad.nombre_corto, ficha.nombre_corto)
        self.assertEqual(self.identidad.codigo, "13")

    def test_registro_anterior_se_conserva_hasta_confirmar_campos(self):
        ficha = Trabajador.objects.create(nombre_completo="SILUPU BECERRA NILSON JESUS", dni="87654321", area="TI")
        self.assertEqual(ficha.nombre_corto, ficha.nombre_completo)
        respuesta = self.client.post(reverse("editar_ficha_trabajador", args=[ficha.pk]), self.datos)
        self.assertEqual(respuesta.status_code, 200)
        ficha.refresh_from_db()
        self.assertEqual(ficha.nombre_corto, "Silupu Nilson")

    def test_validacion_y_segundo_apellido_opcional(self):
        for campo in ("nombres", "apellido_paterno"):
            formulario = TrabajadorForm({**self.datos, campo: "  "})
            self.assertFalse(formulario.is_valid())
            self.assertIn(campo, formulario.errors)
        formulario = TrabajadorForm({**self.datos, "apellido_materno": ""})
        self.assertTrue(formulario.is_valid(), formulario.errors)
        ficha = formulario.save()
        self.assertEqual(ficha.nombre_completo, "Nilson Jesús Silupu")
        formulario = TrabajadorForm({**self.datos, "nombres": "N" * 75, "apellido_paterno": "A" * 50, "apellido_materno": "B" * 50})
        self.assertFalse(formulario.is_valid())

    def test_cuenta_vinculada_usa_nombre_confirmado(self):
        ficha = self.actor.ficha_trabajador
        ficha.nombres = "Nilson Jesús"
        ficha.apellido_paterno = "Silupu"
        ficha.apellido_materno = "Becerra"
        ficha.save()
        self.actor.refresh_from_db()
        self.assertEqual(self.actor.nombre_corto, "Silupu Nilson")
