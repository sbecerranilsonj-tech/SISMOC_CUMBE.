"""El inicio de sesión no acepta destinos externos en `next`."""
from django.test import TestCase
from django.urls import reverse

from core.models import Usuario


class LoginNextSeguroTests(TestCase):
    def test_next_externo_cae_al_inicio(self):
        Usuario.objects.create_user(
            'login-next-seguro', dni='95959595', rol='CONTADORA',
            password='ClaveSegura2026!')
        respuesta = self.client.post(reverse('login'), {
            'username': 'login-next-seguro',
            'password': 'ClaveSegura2026!',
            'next': 'https://sitio-externo.invalid/ruta',
        })
        self.assertEqual(respuesta.status_code, 302)
        destino = respuesta['Location']
        self.assertNotIn('sitio-externo.invalid', destino)
        self.assertEqual(destino, reverse('dashboard'))
