import os
import sqlite3
import tempfile
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
from django.test import SimpleTestCase,TestCase,override_settings
from django.contrib.auth import get_user_model
from desktop.runtime import preparar_entorno,respaldo_antes_de_migrar,InstanciaUnica


class RuntimeTests(SimpleTestCase):
    def test_datos_y_clave_persisten_sin_usar_entorno_railway(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ):
            root=preparar_entorno(d)
            key=(root/'.secret_key').read_text()
            self.assertGreaterEqual(len(key),50)
            self.assertEqual(preparar_entorno(d),root)
            self.assertEqual((root/'.secret_key').read_text(),key)
            self.assertEqual(os.environ['DJANGO_SETTINGS_MODULE'],'config.settings_desktop')
            self.assertEqual(os.environ['SISMOC_LOAD_DOTENV'],'False')
            self.assertTrue((root/'private_bancos').is_dir())

    def test_respaldo_conserva_base_original(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ):
            root=preparar_entorno(d)
            with closing(sqlite3.connect(root/'sismoc.sqlite3')) as conn,conn:
                conn.execute('CREATE TABLE prueba (valor INTEGER)');conn.execute('INSERT INTO prueba VALUES (42)')
            backup=respaldo_antes_de_migrar(root)
            with closing(sqlite3.connect(backup)) as conn:self.assertEqual(conn.execute('SELECT valor FROM prueba').fetchone()[0],42)
            self.assertTrue((root/'sismoc.sqlite3').exists())

    def test_impide_dos_instancias(self):
        if os.name!='nt':self.skipTest('Bloqueo de archivo de Windows')
        with tempfile.TemporaryDirectory() as d:
            with InstanciaUnica(d):
                with self.assertRaises(RuntimeError):
                    with InstanciaUnica(d):pass
            with InstanciaUnica(d):pass


@override_settings(ESCRITORIO=True,MOVIL_HABILITADO=False,ROOT_URLCONF='desktop.test_urls')
class DesktopNavigationTests(TestCase):
    def test_panel_escritorio_no_muestra_modulos_moviles(self):
        u=get_user_model().objects.create_user(username='contabilidad_desktop',dni=None,rol='CONTADORA')
        self.client.force_login(u)
        r=self.client.get('/')
        self.assertEqual(r.status_code,200)
        self.assertContains(r,'Gestión de la empresa')
        self.assertNotContains(r,'Aplicativo de trabajadores')
        self.assertNotContains(r,'Programación y embarque')
        self.assertEqual(self.client.get('/movil/').status_code,404)
        self.assertEqual(self.client.get('/movil/api/login/').status_code,404)
        self.assertEqual(self.client.get('/api/docs').status_code,404)

    def test_ventas_no_redirige_a_app_en_escritorio(self):
        u=get_user_model().objects.create_user(username='ventas_desktop',dni=None,rol='BOLETERIA')
        self.client.force_login(u)
        self.assertEqual(self.client.get('/').status_code,200)
