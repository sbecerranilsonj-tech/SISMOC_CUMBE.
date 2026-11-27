import base64
import hashlib
from datetime import date,time
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from conductores.models import Importacion,Salida,Conductor
from .models import Perfil,Operacion
from .comparacion_itinerarios import comparar_filas
from .gestion import gestionar
from .views import Problema


class ItinerariosCompartidosTests(TestCase):
    def setUp(self):
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        carpeta=TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        configuracion=override_settings(PRIVATE_CONDUCTORES_ROOT=carpeta.name)
        configuracion.enable();self.addCleanup(configuracion.disable)
        self.u=get_user_model().objects.create_user(username='boleteria.test',rol='BOLETERIA',dni=None,agencia_sede='Chiclayo')
        self.p=Perfil.objects.create(usuario=self.u)
        self.client.force_login(self.u)
        self.lote=Importacion.objects.create(nombre='Yaneli.xlsx',huella=hashlib.sha256(b'archivo').hexdigest(),inicio=date(2026,8,1),fin=date(2026,8,1),estado='VALIDADO',creado_por=self.u)
        self.c1=Conductor.objects.create(nombre='UNO PRUEBA')
        self.c2=Conductor.objects.create(nombre='DOS PRUEBA')
        self.f={'fila':3,'fecha':date(2026,8,1),'hora':time(7),'bus':'BUS1','origen':'Chiclayo - Terminal Central','destino':'Cajamarca - Terminal','nombre_uno':'UNO PRUEBA','nombre_dos':'DOS PRUEBA','anulado':False,'clave':'b'*64,'correlativo':'001','original':{'comercial':{'capacidad':60,'vendidos_primer_piso':20,'vendidos_segundo_piso':25}}}
        self.s=Salida.objects.create(importacion=self.lote,conductor_uno=self.c1,conductor_dos=self.c2,clave_confirmada=self.f['clave'],**self.f)

    def test_panel_muestra_itinerario_contabilidad_sin_operacion(self):
        response=self.client.get('/movil/ventas/?mes=2026-08')
        self.assertContains(response,'Yaneli.xlsx')
        self.assertNotContains(response,'Configurar viaje')
        self.assertNotContains(response,'Mi asistencia')
        self.assertContains(response,'id="cd-itinerario-file"')
        self.assertFalse(Operacion.objects.exists())
        self.client.post('/movil/buses/',{'accion':'abrir','salida':self.s.pk})
        self.assertEqual(Operacion.objects.get().salida_id,self.s.pk)
        self.assertEqual(Salida.objects.count(),1)

    def test_formato_reporte_y_filtros_estado(self):
        Salida.objects.create(importacion=self.lote,**{**self.f,'fila':4,'hora':time(6),'clave':'c'*64,'anulado':True})
        response=self.client.get('/movil/ventas/')
        self.assertEqual([s.fila for s in response.context['registro_pagina']],[3,4])
        self.assertContains(response,'Vendidos 1.er piso')
        self.assertContains(response,'Conductor N.º 2')
        self.assertContains(response,'cd-month-filters')
        self.assertNotContains(response,'name="desde"')
        self.assertEqual(response.context['validadas'],1)
        self.assertEqual(response.context['anuladas'],1)
        response=self.client.get('/movil/ventas/?estado=anuladas')
        self.assertEqual([s.fila for s in response.context['registro_pagina']],[4])

    def test_viajes_pasados_realizados_no_muestran_gestion(self):
        respuesta=self.client.get('/movil/ventas/?mes=2026-08')
        self.assertNotContains(respuesta,'Gestionar viaje y responsable de embarque')
        self.s.estado_operativo='REALIZADO'
        self.s.save(update_fields=['estado_operativo'])
        respuesta=self.client.get('/movil/ventas/?mes=2026-08')
        self.assertNotContains(respuesta,'Gestionar viaje y responsable de embarque')
        Salida.objects.create(importacion=self.lote,clave_confirmada='d'*64,
            **{**self.f,'fila':5,'fecha':timezone.localdate(),'hora':time(9),'clave':'d'*64})
        respuesta=self.client.get('/movil/ventas/')
        self.assertContains(respuesta,'Gestionar viaje y responsable de embarque')

    def test_comparacion_detecta_ventas_y_hora_sin_duplicar(self):
        self.assertEqual(comparar_filas([self.f])[0]['estado'],'EXISTENTE')
        f={**self.f,'hora':time(8),'clave':'c'*64,'original':{'comercial':{'capacidad':60,'vendidos_primer_piso':21,'vendidos_segundo_piso':25}}}
        c=comparar_filas([f])[0]
        self.assertEqual(c['estado'],'CAMBIO')
        self.assertEqual({d['campo'] for d in c['diferencias']},{'Hora','Ventas piso 1'})
        self.assertEqual(Salida.objects.count(),1)

    def test_reimportar_archivo_de_yaneli_vincula_sin_duplicar(self):
        with patch('conductores.parser.extraer',return_value=([self.f],[])):
            with transaction.atomic():
                gestionar('importar_itinerario',self.p,{'nombre':'nuevo.xlsx','contenido':base64.b64encode(b'archivo').decode()})
        self.assertEqual(Salida.objects.count(),1)
        self.assertEqual(Importacion.objects.count(),1)
        self.assertEqual(Operacion.objects.count(),1)

    def test_otro_archivo_con_mismos_viajes_no_crea_lote_vacio(self):
        with patch('conductores.parser.extraer',return_value=([self.f],[])):
            with transaction.atomic():
                gestionar('importar_itinerario',self.p,{'nombre':'copia.xlsx','contenido':base64.b64encode(b'otra presentacion').decode()})
        self.assertEqual(Salida.objects.count(),1)
        self.assertEqual(Importacion.objects.count(),1)
        self.assertEqual(Operacion.objects.count(),1)

    def test_cambio_muestra_antes_y_despues_y_no_modifica(self):
        f={**self.f,'bus':'BUS2'}
        with patch('conductores.parser.extraer',return_value=([f],[])):
            self.client.post('/movil/ventas/',{'accion':'importar_itinerario','archivo':SimpleUploadedFile('cambio.xlsx',b'cambio')})
        self.s.refresh_from_db();self.assertEqual(self.s.bus,'BUS1')
        self.assertEqual(Importacion.objects.count(),1)
        response=self.client.get('/movil/ventas/')
        self.assertContains(response,'BUS1');self.assertContains(response,'BUS2')
        self.assertContains(response,'data-revision-itinerario')
        self.assertNotContains(response,'Sin diferencias')

    def test_archivo_pendiente_no_se_vincula(self):
        self.lote.estado='PENDIENTE';self.lote.save()
        self.assertEqual(comparar_filas([self.f])[0]['estado'],'PENDIENTE')
        self.client.post('/movil/buses/',{'accion':'abrir','salida':self.s.pk})
        self.assertFalse(Operacion.objects.exists())

    def subir_cambio(self):
        f={**self.f,'bus':'BUS2'}
        with patch('conductores.parser.extraer',return_value=([f],[])):
            self.client.post('/movil/ventas/',{'accion':'importar_itinerario','archivo':SimpleUploadedFile('revision.xlsx',b'revision')})
        return self.client.session['revision_itinerario']

    def test_popup_permite_editar_validar_y_actualizar_misma_salida(self):
        revision=self.subir_cambio()
        self.client.post('/movil/ventas/',{'accion':'validar_comparacion','revision':revision['token'],'c_3_bus':'BUS3'})
        self.s.refresh_from_db();self.assertEqual(self.s.bus,'BUS3')
        self.assertEqual(Salida.objects.count(),1)
        self.assertNotIn('revision_itinerario',self.client.session)
        self.assertNotContains(self.client.get('/movil/ventas/'),'data-revision-itinerario')

    def test_popup_permite_conservar_ficha_existente(self):
        revision=self.subir_cambio()
        respuesta=self.client.get('/movil/ventas/')
        self.assertContains(respuesta,'Ficha registrada')
        self.assertContains(respuesta,'Ficha del Excel')
        self.assertContains(respuesta,'name="eleccion_3"')
        self.client.post('/movil/ventas/',{
            'accion':'validar_comparacion','revision':revision['token'],
            'eleccion_3':'conservar',
        })
        self.s.refresh_from_db()
        self.assertEqual(self.s.bus,'BUS1')
        self.assertEqual(Salida.objects.count(),1)

    def test_popup_permite_elegir_ficha_excel(self):
        revision=self.subir_cambio()
        self.client.post('/movil/ventas/',{
            'accion':'validar_comparacion','revision':revision['token'],
            'eleccion_3':'excel',
        })
        self.s.refresh_from_db()
        self.assertEqual(self.s.bus,'BUS2')
        self.assertEqual(Salida.objects.count(),1)

    def test_revision_obsoleta_no_sobrescribe_cambio_ajeno(self):
        revision=self.subir_cambio()
        Salida.objects.filter(pk=self.s.pk).update(bus='CAMBIO AJENO')
        response=self.client.post('/movil/ventas/',{'accion':'validar_comparacion','revision':revision['token'],'c_3_bus':'BUS3'},follow=True)
        self.assertContains(response,'El itinerario cambió')
        self.s.refresh_from_db();self.assertEqual(self.s.bus,'CAMBIO AJENO')

    def test_descartar_revision_no_modifica_salida(self):
        self.subir_cambio()
        self.client.post('/movil/ventas/',{'accion':'descartar_comparacion'})
        self.s.refresh_from_db();self.assertEqual(self.s.bus,'BUS1')
        self.assertNotIn('revision_itinerario',self.client.session)

    def test_sin_cambios_no_muestra_comparacion_y_aviso_caduca(self):
        with patch('conductores.parser.extraer',return_value=([self.f],[])):
            self.client.post('/movil/ventas/',{'accion':'importar_itinerario','archivo':SimpleUploadedFile('igual.xlsx',b'archivo')})
        response=self.client.get('/movil/ventas/')
        self.assertNotContains(response,'data-revision-itinerario')
        self.assertContains(response,'data-auto-dismiss="5000"')
        self.assertEqual(response.content.decode().count('sus viajes están vinculados sin duplicarlos.'),1)

    def test_cuenta_sede_unica_sin_ficha_personal(self):
        from core.cuentas_sede import crear_cuenta_sede
        from asistencia.models import Trabajador
        u=crear_cuenta_sede('Chiclayo','sede.chiclayo','Seguro-Zona-8249!')
        self.assertIsNone(u.dni)
        self.assertFalse(Trabajador.objects.filter(usuario=u).exists())
        with self.assertRaises(ValidationError):crear_cuenta_sede(' CHICLAYO ','otra.sede','Seguro-Zona-8249!')
        self.assertTrue(get_user_model().objects.filter(pk=self.u.pk).exists())
