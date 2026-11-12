from datetime import date, time
from io import BytesIO
from unittest.mock import patch, Mock
from tempfile import TemporaryDirectory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from core.models import Usuario
from .models import Conductor, IdentidadConductor, Importacion, Salida, SituacionConductor, Auditoria
from .parser import interpretar_filas, identidad, extraer, abrir_xls
from .services import calendario, confirmar, registrar_situacion, registrar_conductores_reporte, problemas, reconocer_registrados


class ConductoresTests(TestCase):
    def test_cero_ventas_no_genera_trayectos_ni_pago_y_se_conserva_asignacion(self):
        salida=self.salida(16, original={'comercial':{'vendidos_primer_piso':0,'vendidos_segundo_piso':0}})
        confirmar(self.lote.pk,self.usuario)
        filas=calendario(self.fecha,self.fecha)[1]
        self.assertEqual({f['conductor'].pk for f in filas},{self.a.pk,self.b.pk})
        for fila in filas:
            self.assertEqual((fila['trayectos'],fila['vueltas'],fila['pago_vueltas'],fila['horas'],fila['una_x'],fila['dos_x']),(0,0,0,0,0,0))
            self.assertEqual(fila['celdas'][0]['etiqueta'],'SV')
            self.assertEqual(fila['celdas'][0]['excluidas'],[salida])
        self.assertContains(self.client.get(reverse('conductores_control')),'Confirmar que salió')
        response=self.client.post(reverse('conductores_resolver_salida',args=[salida.pk]),{'decision':'CANCELADO'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(calendario(self.fecha,self.fecha)[1][0]['celdas'][0]['etiqueta'],'C')
        salida.refresh_from_db()
        self.assertEqual(salida.original['comercial']['vendidos_primer_piso'],0)
        self.assertFalse(salida.anulado)
        self.assertTrue(self.lote.historial.filter(mensaje__contains='Confirmación operativa').exists())
        self.assertEqual(self.client.post(reverse('conductores_resolver_salida',args=[salida.pk]),{'decision':'REALIZADO'}).status_code,200)
        self.assertEqual(calendario(self.fecha,self.fecha)[1][0]['pago_vueltas'],10)

    def test_una_venta_cuenta_y_no_hay_umbral_arbitrario(self):
        self.salida(7,original={'comercial':{'vendidos_primer_piso':0,'vendidos_segundo_piso':1}})
        confirmar(self.lote.pk,self.usuario)
        self.assertEqual(calendario(self.fecha,self.fecha)[1][0]['trayectos'],1)

    def test_cancelada_no_suma_en_un_dia_con_otros_viajes(self):
        self.salida(7)
        self.salida(14,original={'10':'0','12':'0'})
        self.salida(23,anulado=True)
        confirmar(self.lote.pk,self.usuario)
        fila=calendario(self.fecha,self.fecha)[1][0]
        self.assertEqual((fila['trayectos'],fila['pago_vueltas'],fila['horas'],fila['una_x']),(1,10,1,0))
        self.assertEqual(len(fila['celdas'][0]['excluidas']),2)

    def test_sin_asignaciones_ni_situaciones_se_oculta_y_catalogo_lo_conserva(self):
        self.assertEqual(calendario(self.fecha,self.fecha)[1],[])
        self.assertContains(self.client.get(reverse('conductores_catalogo')),self.c.nombre_apellidos)
        registrar_situacion(self.c,self.fecha,self.fecha,'DESCANSO','',self.usuario)
        self.assertEqual([f['conductor'].pk for f in calendario(self.fecha,self.fecha)[1]],[self.c.pk])

    def test_realizar_con_situacion_y_anulado_no_se_permite(self):
        salida=self.salida(7,original={'comercial':{'vendidos_primer_piso':0,'vendidos_segundo_piso':0}})
        confirmar(self.lote.pk,self.usuario)
        registrar_situacion(self.a,self.fecha,self.fecha,'DESCANSO','',self.usuario)
        self.assertEqual(self.client.post(reverse('conductores_resolver_salida',args=[salida.pk]),{'decision':'REALIZADO'}).status_code,400)
        salida.anulado=True;salida.save()
        self.assertEqual(self.client.post(reverse('conductores_resolver_salida',args=[salida.pk]),{'decision':'REALIZADO'}).status_code,400)
        self.usuario.rol='CONDUCTOR';self.usuario.save()
        self.assertEqual(self.client.post(reverse('conductores_resolver_salida',args=[salida.pk]),{'decision':'CANCELADO'}).status_code,403)

    def test_resumen_incluye_todos_con_ceros_sin_agregarlos_al_calendario(self):
        self.salida(7);confirmar(self.lote.pk,self.usuario)
        parametros={'desde':'2026-07-31','hasta':'2026-07-31'}
        response=self.client.get(reverse('conductores_control'),parametros)
        self.assertEqual({f['conductor'].pk for f in response.context['filas']},{self.a.pk,self.b.pk})
        resumen=response.context['filas_resumen']
        self.assertEqual({f['conductor'].pk for f in resumen},{self.a.pk,self.b.pk,self.c.pk})
        inactivo=next(f for f in resumen if f['conductor']==self.c)
        for campo in ('trayectos','trabajados','descansos','vueltas','pago_vueltas','horas','una_x','dos_x','pendientes'):
            self.assertEqual(inactivo[campo],0)
        from openpyxl import load_workbook
        libro=load_workbook(BytesIO(self.client.get(reverse('conductores_exportar_calendario'),parametros).content))
        hoja=libro['Resumen del período']
        fila=next(r for r in hoja.iter_rows(min_row=5,values_only=True) if r[0]==self.c.nombre_apellidos)
        self.assertEqual(fila[1:],(0,)*9)
        response=self.client.get(reverse('conductores_control'),{**parametros,'q':'OTRO'})
        self.assertEqual([f['conductor'].pk for f in response.context['filas_resumen']],[self.c.pk])

    def test_lista_de_confirmacion_no_duplica_salida_y_senala_dias_mixtos(self):
        self.salida(7)
        pendiente=self.salida(14,original={'10':'0','12':'0'})
        confirmar(self.lote.pk,self.usuario)
        response=self.client.get(reverse('conductores_control'))
        self.assertEqual([s.pk for s in response.context['salidas_por_confirmar']],[pendiente.pk])
        self.assertContains(response, 'Salidas por confirmar · 1')
        self.assertContains(response, '<small class="cd-sv-mark">SV 1</small>', count=2)
        fila=response.context['filas'][0]
        self.assertEqual((fila['celdas'][0]['cantidad'],fila['celdas'][0]['sin_ventas']),(1,1))
        self.client.post(reverse('conductores_resolver_salida',args=[pendiente.pk]),{'decision':'REALIZADO'})
        response=self.client.get(reverse('conductores_control'))
        self.assertEqual(response.context['salidas_por_confirmar'],[])
        self.assertEqual(response.context['filas'][0]['celdas'][0]['etiqueta'],'X')
        self.assertNotContains(response, '<small class="cd-sv-mark">SV 1</small>')

    def test_totales_resumen_suman_conductores_y_respetan_filtros(self):
        self.salida(7);confirmar(self.lote.pk,self.usuario)
        response=self.client.get(reverse('conductores_control'))
        t=response.context['totales']
        self.assertEqual((t['trayectos'],t['vueltas'],t['pago_vueltas'],t['horas'],t['una_x'],t['dos_x']),(2,1,20,2,0,0))
        self.assertContains(response,'<tfoot>')
        response=self.client.get(reverse('conductores_control'),{'desde':'2026-07-31','hasta':'2026-07-31','q':'ELBER'})
        t=response.context['totales']
        self.assertEqual((t['vueltas'],t['pago_vueltas'],t['horas']),(0.5,10,1))
    def test_motivo_opcional_y_descuento_desde_ficha(self):
        response=self.client.post(reverse('conductores_ficha'),{'accion':'situacion','id':self.a.pk,'tipo':'DESCUENTO','inicio':'2026-07-31','fin':'2026-07-31'})
        self.assertContains(response,'Situación guardada')
        situacion=SituacionConductor.objects.get()
        self.assertEqual(situacion.motivo,'')
        fila=next(f for f in calendario(self.fecha,self.fecha)[1] if f['conductor']==self.a)
        self.assertEqual(fila['celdas'][0]['etiqueta'],'DS')
        self.assertEqual(fila['pendientes'],0)

    def test_pago_por_vuelta_usa_decimales_y_columna_en_orden(self):
        self.salida(7);confirmar(self.lote.pk,self.usuario)
        fila=next(f for f in calendario(self.fecha,self.fecha)[1] if f['conductor']==self.a)
        self.assertEqual(fila['vueltas'],0.5)
        self.assertEqual(str(fila['pago_vueltas']),'10.00')
        response=self.client.get(reverse('conductores_control'))
        html=response.content.decode()
        resumen=html[html.index('id="resumen-conductores"'):]
        etiquetas=['<th>Trayectos</th>','<th>Días con viajes</th>','<th>Descansos</th>','<th>Vueltas</th>','<th>Pago por vueltas','<th>HORA</th>','<th>X</th>','<th>XX</th>','<th>Pendientes</th>']
        posiciones=[resumen.index(t) for t in etiquetas]
        self.assertEqual(posiciones,sorted(posiciones))
        self.assertContains(response,'S/ 10.00')
    def test_editar_situacion_del_dia_actualiza_calendario_y_auditoria(self):
        s=registrar_situacion(self.a,self.fecha,self.fecha,'DESCANSO','',self.usuario)
        response=self.client.post(reverse('conductores_situacion_dia'),{'conductor':self.a.pk,'situacion_id':s.pk,'tipo':'VACACIONES','inicio':'2026-07-31','fin':'2026-07-31'})
        self.assertEqual(response.status_code,200)
        s.refresh_from_db();self.assertFalse(s.activa)
        fila=next(f for f in calendario(self.fecha,self.fecha)[1] if f['conductor']==self.a)
        self.assertEqual(fila['celdas'][0]['etiqueta'],'V')
        self.assertEqual(fila['descansos'],0)
        self.assertTrue(s.auditoria_set.filter(mensaje__contains='Se cambió').exists())
        self.assertContains(self.client.get(reverse('conductores_control'),{'desde':'2026-07-31','hasta':'2026-07-31'}),'data-edit-day')

    def test_editar_un_dia_conserva_el_resto_del_periodo_y_rechaza_id_ajeno(self):
        s=registrar_situacion(self.a,date(2026,7,30),date(2026,8,1),'VACACIONES','Aprobadas',self.usuario)
        datos={'conductor':self.b.pk,'situacion_id':s.pk,'tipo':'DESCANSO','inicio':'2026-07-31','fin':'2026-07-31'}
        self.assertEqual(self.client.post(reverse('conductores_situacion_dia'),datos).status_code,400)
        datos['conductor']=self.a.pk
        self.assertEqual(self.client.post(reverse('conductores_situacion_dia'),datos).status_code,200)
        fila=next(f for f in calendario(date(2026,7,30),date(2026,8,1))[1] if f['conductor']==self.a)
        self.assertEqual([c['etiqueta'] for c in fila['celdas']],['V','D','V'])
        self.assertEqual((fila['vacaciones'],fila['descansos']),(2,1))
    def test_resumen_cuenta_dias_hora_x_y_xx_separados(self):
        self.salida(7)
        for hora in (14,23):
            s=self.salida(hora);s.fecha=date(2026,8,1);s.save()
        for hora in (8,9,10):
            s=self.salida(hora);s.fecha=date(2026,8,2);s.save()
        confirmar(self.lote.pk,self.usuario)
        registrar_situacion(self.a,date(2026,8,3),date(2026,8,3),'DESCANSO','Programado',self.usuario)
        fila=next(f for f in calendario(self.fecha,date(2026,8,3))[1] if f['conductor']==self.a)
        self.assertEqual((fila['horas'],fila['una_x'],fila['dos_x']),(1,1,1))
        self.assertEqual((fila['trayectos'],fila['vueltas'],fila['trabajados'],fila['descansos']),(6,3,3,1))

    def test_calendario_sin_totales_y_resumen_independiente(self):
        self.salida(7);confirmar(self.lote.pk,self.usuario)
        response=self.client.get(reverse('conductores_control'))
        self.assertContains(response,'id="resumen-conductores"')
        self.assertContains(response,'<th>HORA</th>')
        self.assertContains(response,'<th>XX</th>')
        self.assertNotContains(response,'<th>Vacaciones</th>')
        self.assertNotContains(response,'<th>Permisos</th>')
        self.assertNotContains(response,'<th scope="row">Pasajes vendidos</th>')
        self.assertNotContains(response,'<th scope="row">Capacidad</th>')

    def test_dia_pendiente_permite_registrar_situacion_y_actualiza_calendario(self):
        self.salida(7,original={'10':'0','12':'0'});confirmar(self.lote.pk,self.usuario)
        response=self.client.get(reverse('conductores_control'))
        self.assertContains(response,'data-day-situation')
        datos={'conductor':self.a.pk,'tipo':'DESCANSO','inicio':'2026-07-31','fin':'2026-07-31'}
        response=self.client.post(reverse('conductores_situacion_dia'),datos)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['ok'])
        fila=next(f for f in calendario(self.fecha,self.fecha)[1] if f['conductor']==self.a)
        self.assertEqual(fila['celdas'][0]['etiqueta'],'D')
        self.assertEqual(fila['descansos'],1)
        self.assertEqual(fila['pendientes'],0)
        self.assertEqual(self.client.post(reverse('conductores_situacion_dia'),datos).status_code,400)
        self.assertEqual(SituacionConductor.objects.count(),1)

    def test_situacion_desde_calendario_admite_rango_y_actualiza_todos_los_dias(self):
        datos={'conductor':self.a.pk,'tipo':'DESCANSO','inicio':'2026-08-01','fin':'2026-08-04'}
        self.assertEqual(self.client.post(reverse('conductores_situacion_dia'),datos).status_code,200)
        fila=next(f for f in calendario(date(2026,8,1),date(2026,8,4))[1] if f['conductor']==self.a)
        self.assertEqual([c['etiqueta'] for c in fila['celdas']],['D']*4)
        self.assertEqual(fila['descansos'],4)
        situacion=SituacionConductor.objects.get(conductor=self.a)
        datos.update(situacion_id=situacion.pk, tipo='VACACIONES', inicio='2026-08-02', fin='2026-08-03')
        self.assertEqual(self.client.post(reverse('conductores_situacion_dia'),datos).status_code,200)
        fila=next(f for f in calendario(date(2026,8,1),date(2026,8,4))[1] if f['conductor']==self.a)
        self.assertEqual([c['etiqueta'] for c in fila['celdas']],['D','V','V','D'])

    def test_excel_calendario_incluye_resumen_totales_y_filtro(self):
        from openpyxl import load_workbook
        self.salida(7);confirmar(self.lote.pk,self.usuario)
        response=self.client.get(reverse('conductores_exportar_calendario'),{'desde':'2026-07-31','hasta':'2026-07-31','q':'QUISPE'})
        self.assertEqual(response.status_code,200)
        wb=load_workbook(BytesIO(response.content))
        self.assertEqual(wb.sheetnames,['Calendario','Resumen del período'])
        self.assertEqual(wb['Calendario']['B5'].value,'07:00')
        self.assertEqual(wb['Calendario'].max_row,5)
        self.assertEqual(wb['Calendario'].freeze_panes,'B5')
        resumen=wb['Resumen del período']
        self.assertEqual(resumen['E5'].value,.5)
        self.assertEqual(resumen['F5'].value,10)
        self.assertEqual(resumen['A6'].value,'TOTAL')
        self.assertEqual(resumen['F6'].value,10)
        self.assertEqual(self.client.get(reverse('conductores_exportar_calendario')).status_code,400)

    def test_situacion_directa_no_admite_viajes_ni_rango_de_dias(self):
        self.salida(7);confirmar(self.lote.pk,self.usuario)
        datos={'conductor':self.a.pk,'tipo':'VACACIONES','inicio':'2026-07-31','fin':'2026-07-31','motivo':'Autorizadas'}
        self.assertEqual(self.client.post(reverse('conductores_situacion_dia'),datos).status_code,400)
        datos['fin']='2026-08-01'
        self.assertEqual(self.client.post(reverse('conductores_situacion_dia'),datos).status_code,400)
        self.assertEqual(SituacionConductor.objects.count(),0)
        self.usuario.rol='CONDUCTOR';self.usuario.save()
        self.assertEqual(self.client.post(reverse('conductores_situacion_dia'),datos).status_code,403)
    def test_importar_muestra_filas_en_orden_original_del_excel(self):
        tarde=self.salida(23)
        temprano=self.salida(7)
        tarde.fila=3;tarde.save()
        temprano.fila=4;temprano.save()
        response=self.client.get(reverse('conductores_importar'))
        self.assertEqual([s.pk for s in response.context['pagina_salidas']],[tarde.pk,temprano.pk])
        for titulo in ('Fecha / hora','Recorrido','Conductor N.º 1','Conductor N.º 2','Vendidos 1.er piso','Vendidos 2.º piso','Total vendidos','Capacidad','Estado'):
            self.assertContains(response,titulo)
        self.assertNotContains(response,'Conductor del reporte')
        self.assertNotContains(response,'Cada nombre se muestra una vez por archivo')

    def test_carga_directa_no_usa_popup(self):
        response=self.client.get(reverse('conductores_importar'))
        self.assertContains(response,'data-upload-directo')
        self.assertContains(response,'id="cd-itinerario-file"')
        self.assertNotContains(response,'id="importar-dialog"')
        self.assertNotContains(response,'data-open="importar-dialog"')

    def test_filas_anuladas_visibles_sin_pasar_a_control(self):
        self.salida(7); anulada=self.salida(14,anulado=True)
        response=self.client.get(reverse('conductores_importar'),{'estado':'anuladas'})
        self.assertEqual(response.context['anuladas'],1)
        self.assertEqual([s.pk for s in response.context['pagina_salidas']],[anulada.pk])
        self.assertEqual(response.context['total_filas'],2)

    def test_confirmar_desde_importar_reutiliza_validaciones(self):
        self.salida(7)
        response=self.client.get(reverse('conductores_importar'),{'archivo':self.lote.pk})
        self.assertContains(response,'Confirmar y pasar a control de conductores')
        self.client.post(reverse('conductores_detalle',args=[self.lote.pk]),{'accion':'confirmar'})
        self.lote.refresh_from_db();self.assertEqual(self.lote.estado,'VALIDADO')
        response=self.client.get(reverse('conductores_importar'),{'estado':'validadas'})
        self.assertEqual(response.context['validadas'],1)
        self.assertContains(response,'Reporte validado')
    def test_listado_meses_usa_fecha_de_salida_no_mes_de_carga(self):
        self.salida(7)
        s=self.salida(14); s.fecha=date(2026,8,1); s.save()
        respuesta=self.client.get(reverse('conductores_importar'),{'mes':'2026-08'})
        self.assertEqual(respuesta.context['total_salidas'],1)
        self.assertEqual({m['valor'] for m in respuesta.context['meses']},{'2026-07','2026-08'})
        self.assertEqual(respuesta.context['reconocidos'],2)
        self.assertContains(respuesta,'Agosto 2026')
        self.assertContains(respuesta,'Subir itinerarios')

    def test_listado_filtros_pendientes_reconocidos_y_archivo(self):
        s=self.salida(7); s.conductor_dos=None; s.save()
        respuesta=self.client.get(reverse('conductores_importar'),{'estado':'pendientes','archivo':self.lote.pk})
        self.assertEqual(respuesta.context['pendientes_total'],1)
        self.assertEqual(respuesta.context['reconocidos'],1)
        self.assertEqual(len(respuesta.context['identidades']),1)
        self.assertEqual(respuesta.context['identidades'][0]['nombre'],self.b.nombre)
        confirmar_luego=self.client.get(reverse('conductores_importar'),{'mes':'invalido'})
        self.assertEqual(confirmar_luego.status_code,200)

    def test_reconocer_no_crea_fichas_y_resuelve_solo_nombres_existentes(self):
        s=self.salida(7); s.conductor_uno=None; s.conductor_dos=None; s.nombre_dos='PERSONA SIN REGISTRO'; s.save()
        self.assertEqual(reconocer_registrados(self.lote.pk,self.usuario),1)
        s.refresh_from_db(); self.assertEqual(s.conductor_uno,self.a); self.assertIsNone(s.conductor_dos)
        self.assertEqual(Conductor.objects.count(),3)

    def test_configuracion_guarda_apellidos_conserva_fuente_y_reconoce_alias(self):
        response=self.client.post(reverse('conductores_configuracion'),{'id':self.a.pk,'nombres':'Elber','apellido_paterno':'Quispe','apellido_materno':'Saavedra'})
        self.assertContains(response,'Datos guardados')
        self.a.refresh_from_db(); self.assertEqual(self.a.nombre_apellidos,'QUISPE SAAVEDRA ELBER')
        self.assertEqual(self.a.nombre,'ELBER QUISPE SAAVEDRA')
        self.assertTrue(IdentidadConductor.objects.filter(conductor=self.a).exists())
        self.assertTrue(Auditoria.objects.filter(mensaje__contains='configuración').exists())

    def test_configuracion_crea_conductor_y_rechaza_duplicado(self):
        datos={'nombres':'Ana Maria','apellido_paterno':'Perez','apellido_materno':'Lopez'}
        self.assertContains(self.client.post(reverse('conductores_configuracion'),datos),'Datos guardados')
        self.assertEqual(Conductor.objects.count(),4)
        self.assertContains(self.client.post(reverse('conductores_configuracion'),datos),'otro conductor registrado')
        self.assertEqual(Conductor.objects.count(),4)

    def test_configuracion_invalida_no_guarda_y_permiso_es_obligatorio(self):
        self.assertContains(self.client.post(reverse('conductores_configuracion'),{'nombres':'Sin apellido'}),'errorlist')
        self.assertEqual(Conductor.objects.count(),3)
        self.usuario.rol='CONDUCTOR'; self.usuario.save()
        self.assertEqual(self.client.get(reverse('conductores_configuracion')).status_code,403)
        self.assertEqual(self.client.post(reverse('conductores_configuracion'),{}).status_code,403)

    def test_control_abre_conductores_en_recuadro_de_cabecera(self):
        respuesta=self.client.get(reverse('conductores_control'))
        self.assertContains(respuesta,'data-config-open')
        self.assertContains(respuesta,'id="configuracion-conductores"')
        self.assertNotContains(respuesta,'Gestionar conductores')
        self.assertNotContains(respuesta,'class="cd-emblema"')
        self.assertNotContains(respuesta,'id="situacion-dialog"')

    def test_menu_unificado_y_ruta_anterior_redirige(self):
        respuesta=self.client.get(reverse('conductores_importar'))
        self.assertNotContains(respuesta,'<nav class="cd-tabs"')
        self.assertNotContains(respuesta,'data-conductores="validacion"')
        self.assertNotContains(respuesta,'data-conductores="catalogo"')
        self.assertRedirects(self.client.get(reverse('conductores_validacion'),{'mes':'2026-08'}),reverse('conductores_importar')+'?mes=2026-08')

    def test_popup_incluye_configuracion_y_situaciones_sin_pagina_completa(self):
        response=self.client.get(reverse('conductores_catalogo'),HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response,'Registrar nuevo')
        self.assertContains(response,'Configurar')
        self.assertNotContains(response,'Editar datos')
        self.assertContains(response,'data-close-config')
        self.assertNotContains(response,'<details')
        self.assertContains(response,'data-config-form')
        self.assertNotContains(response,'<html')

    def test_popup_guarda_y_anula_situacion_sin_abandonar_ventana(self):
        response=self.client.post(reverse('conductores_catalogo'),{'accion':'situacion','conductor':self.a.pk,'tipo':'VACACIONES','inicio':'2026-07-31','fin':'2026-07-31','motivo':'Autorizadas'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'data-actualizado')
        self.assertNotContains(response,'<html')
        s=SituacionConductor.objects.get()
        response=self.client.post(reverse('conductores_anular_situacion',args=[s.pk]),{'origen':'catalogo'},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'data-actualizado')
        s.refresh_from_db();self.assertFalse(s.activa)

    def test_catalogo_permite_licencia_con_y_sin_goce(self):
        for tipo, marca in [('LICENCIA_CG','LC'),('LICENCIA_SG','LS')]:
            response=self.client.post(reverse('conductores_catalogo'),{'accion':'situacion','conductor':self.a.pk,'tipo':tipo,'inicio':'2026-07-31','fin':'2026-07-31','motivo':'Licencia autorizada'})
            self.assertRedirects(response,reverse('conductores_catalogo'))
            fila=next(f for f in calendario(self.fecha,self.fecha)[1] if f['conductor']==self.a)
            self.assertEqual(fila['celdas'][0]['etiqueta'],marca)
            self.assertEqual(fila['permisos'],1)
            s=SituacionConductor.objects.get(activa=True)
            self.assertRedirects(self.client.post(reverse('conductores_anular_situacion',args=[s.pk]),{'origen':'catalogo'}),reverse('conductores_catalogo'))

    def test_catalogo_situacion_invalida_muestra_error(self):
        response=self.client.post(reverse('conductores_catalogo'),{'accion':'situacion','conductor':self.a.pk,'tipo':'VACACIONES','inicio':'2026-08-05','fin':'2026-08-01','motivo':'Vacaciones'})
        self.assertContains(response,'La fecha final')
        self.assertEqual(SituacionConductor.objects.count(),0)
        editor=self.client.get(reverse('conductores_ficha'),{'id':self.a.pk})
        self.assertContains(editor,'Licencia con goce')
        self.assertContains(editor,'Licencia sin goce')

    def test_catalogo_edita_ficha_y_conserva_pagina_completa(self):
        response=self.client.post(reverse('conductores_catalogo'),{'id':self.a.pk,'nombres':'ELBER','apellido_paterno':'QUISPE','apellido_materno':'SAAVEDRA'})
        self.assertContains(response,'Datos del conductor guardados')
        self.assertContains(response,'Configurar')
        self.assertContains(response,'QUISPE SAAVEDRA ELBER')

    def test_editor_individual_guarda_datos_y_situacion_del_conductor(self):
        url=reverse('conductores_ficha')
        response=self.client.get(url,{'id':self.a.pk})
        self.assertContains(response,'Datos del conductor')
        self.assertContains(response,'Vacaciones, descansos y licencias')
        self.assertNotContains(response,'name="conductor"')
        response=self.client.post(url,{'accion':'datos','id':self.a.pk,'nombres':'ELBER','apellido_paterno':'QUISPE','apellido_materno':'SAAVEDRA'})
        self.assertContains(response,'data-actualizado')
        response=self.client.post(url,{'accion':'situacion','id':self.a.pk,'conductor':self.b.pk,'tipo':'LICENCIA_CG','inicio':'2026-07-31','fin':'2026-07-31','motivo':'Autorizada'})
        self.assertContains(response,'Situación guardada y aplicada al calendario')
        self.assertEqual(SituacionConductor.objects.get().conductor,self.a)
        fila=next(f for f in calendario(self.fecha,self.fecha)[1] if f['conductor']==self.a)
        self.assertEqual(fila['celdas'][0]['etiqueta'],'LC')

    def test_editor_registra_nuevo_y_no_guarda_datos_invalidos(self):
        url=reverse('conductores_ficha')
        self.assertContains(self.client.get(url),'Registrar nuevo conductor')
        response=self.client.post(url,{'accion':'datos','nombres':'ANA','apellido_paterno':'PEREZ','apellido_materno':'LOPEZ'})
        self.assertContains(response,'data-actualizado')
        self.assertContains(response,'Vacaciones, descansos y licencias')
        self.assertEqual(Conductor.objects.count(),4)
        self.assertContains(self.client.post(url,{'accion':'datos','nombres':'Sin apellidos'}),'errorlist')
        self.assertEqual(Conductor.objects.count(),4)

    def test_editor_individual_anula_y_conserva_auditoria(self):
        s=registrar_situacion(self.a,self.fecha,self.fecha,'VACACIONES','Autorizadas',self.usuario)
        response=self.client.post(reverse('conductores_anular_situacion',args=[s.pk]),{'editor_id':self.a.pk},HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertContains(response,'data-editor-content')
        self.assertContains(response,'data-actualizado')
        s.refresh_from_db();self.assertFalse(s.activa)

    def test_editor_no_permite_acceso_sin_rol(self):
        self.usuario.rol='CONDUCTOR';self.usuario.save()
        self.assertEqual(self.client.get(reverse('conductores_ficha'),{'id':self.a.pk}).status_code,403)
    def test_control_apellidos_primero_y_orden_alfabetico(self):
        self.salida(7);confirmar(self.lote.pk,self.usuario)
        self.assertEqual(self.a.nombre_apellidos,'QUISPE SAAVEDRA ELBER')
        self.assertEqual(self.b.nombre_apellidos,'LOPEZ GALLARDO CARLOS ALBERTO')
        filas=calendario(self.fecha,self.fecha)[1]
        nombres=[f['conductor'].nombre_apellidos for f in filas]
        self.assertLess(nombres.index(self.b.nombre_apellidos),nombres.index(self.a.nombre_apellidos))
        self.assertEqual(calendario(self.fecha,self.fecha,'QUISPE SAAVEDRA ELBER')[1][0]['conductor'],self.a)
        self.a.refresh_from_db(); self.assertEqual(self.a.nombre,'ELBER QUISPE SAAVEDRA')
        self.assertEqual(Conductor(nombre='SALDAÑA SANGAY ANSELMO').nombre_apellidos,'SALDAÑA SANGAY ANSELMO')
    def test_registro_grupal_crea_solo_conductores_sin_personal(self):
        for h in (7,14,23):
            s=self.salida(h)
            s.conductor_uno=None; s.conductor_dos=None; s.nombre_uno='NUEVO CONDUCTOR UNO'; s.nombre_dos='NUEVO CONDUCTOR DOS'; s.save()
        nuevos,reconocidos=registrar_conductores_reporte(self.lote.pk,self.usuario)
        self.assertEqual((nuevos,reconocidos),(2,0))
        self.assertFalse(self.lote.salidas.filter(conductor_uno__isnull=True).exists())
        self.assertFalse(self.lote.salidas.filter(conductor_dos__isnull=True).exists())
        self.assertFalse(Conductor.objects.exclude(trabajador__isnull=True).exists())
        self.lote.refresh_from_db(); self.assertEqual(self.lote.estado,'PENDIENTE')
        self.assertEqual(registrar_conductores_reporte(self.lote.pk,self.usuario),(0,2))
        self.assertEqual(Conductor.objects.count(),5)

    def test_registro_grupal_reconoce_nombres_en_otro_orden(self):
        s=self.salida(7); s.nombre_uno='QUISPE SAAVEDRA ELBER'; s.conductor_uno=None; s.conductor_dos=None; s.save()
        self.assertEqual(registrar_conductores_reporte(self.lote.pk,self.usuario),(0,2))
        s.refresh_from_db(); self.assertEqual(s.conductor_uno,self.a)
        self.assertFalse(problemas(self.lote))

    def test_registro_grupal_no_modifica_reportes_validados(self):
        self.salida(7); confirmar(self.lote.pk,self.usuario)
        with self.assertRaises(ValueError): registrar_conductores_reporte(self.lote.pk,self.usuario)

    def test_registro_grupal_ambiguo_no_crea_ni_asigna(self):
        s=self.salida(7); s.conductor_uno=None; s.save()
        Conductor.objects.create(nombre='QUISPE SAAVEDRA ELBER')
        with self.assertRaises(ValueError): registrar_conductores_reporte(self.lote.pk,self.usuario)
        s.refresh_from_db(); self.assertIsNone(s.conductor_uno)

    def test_revision_no_repite_un_aviso_por_cada_salida(self):
        for h in (7,14,23):
            s=self.salida(h); s.conductor_uno=None; s.conductor_dos=None; s.save()
        self.assertEqual(len(problemas(self.lote)),1)
        self.assertFalse(problemas(self.lote,incluir_identidades=False))
        response=self.client.get(reverse('conductores_detalle',args=[self.lote.pk]))
        self.assertContains(response,'Registrar conductores del reporte')
        self.assertNotContains(response,'vincule ambos conductores')
        self.assertNotContains(response,'Vincular a personal')
        self.assertContains(response,'disabled')
        self.client.post(reverse('conductores_detalle',args=[self.lote.pk]),{'accion':'registrar_conductores'})
        self.assertFalse(problemas(self.lote))

    def test_xls_recupera_flujo_ole_si_lector_rechaza_contenedor(self):
        lector = Mock()
        libro = Mock()
        lector.open_workbook.side_effect = [Exception('Workbook corruption'), libro]
        with patch.dict('sys.modules', {'xlrd': lector}), patch('conductores.xls_recovery.flujo_workbook', return_value=b'BIFF'):
            self.assertIs(abrir_xls(b'contenedor'), libro)
        self.assertEqual(lector.open_workbook.call_args.kwargs['file_contents'], b'BIFF')

    def test_xls_irrecuperable_da_error_concreto(self):
        lector = Mock()
        lector.open_workbook.side_effect = Exception('Workbook corruption')
        with patch.dict('sys.modules', {'xlrd': lector}), self.assertRaisesRegex(ValueError, 'Guardar como'):
            abrir_xls(b'archivo invalido')

    def test_recuperacion_rechaza_archivo_ajeno(self):
        from .xls_recovery import flujo_workbook
        with self.assertRaises(ValueError): flujo_workbook(b'no es xls')

    def test_ventas_por_piso_no_se_duplican_por_tener_dos_conductores(self):
        filas,errores=interpretar_filas([['Fecha','Hora','Bus','Origen','Destino','Capacidad','Vend 2Do Piso','Vend 1Er Piso'],['2026/07/31','7:00 am','BUS','Chiclayo','Cajamarca',60,42,12]])
        self.assertFalse(errores)
        salida=Salida(**filas[0])
        self.assertEqual(salida.comercial['capacidad'],60)
        self.assertEqual(salida.comercial['vendidos_segundo_piso'],42)
        self.assertEqual(salida.pasajes_vendidos,54)

    def test_ventas_ausentes_no_se_inventan(self):
        self.assertIsNone(Salida(original={}).pasajes_vendidos)
        self.assertEqual(Salida(original={'9':'60.0','10':'42.0','12':'12.0'}).pasajes_vendidos,54)

    def test_ventas_fraccionarias_se_observan(self):
        filas,errores=interpretar_filas([['Fecha','Hora','Bus','Origen','Destino','Vend 1Er Piso'],['2026/07/31','7:00 am','BUS','Chiclayo','Cajamarca',1.5]])
        self.assertTrue(errores)
        self.assertNotIn('vendidos_primer_piso',filas[0]['original']['comercial'])

    def setUp(self):
        self.usuario = Usuario.objects.create_user(username='contadora_rutas', email='rutas@example.test', dni='95100001', password='prueba', rol='CONTADORA')
        self.client.force_login(self.usuario)
        self.a = Conductor.objects.create(nombre='ELBER QUISPE SAAVEDRA')
        self.b = Conductor.objects.create(nombre='CARLOS ALBERTO LOPEZ GALLARDO')
        self.c = Conductor.objects.create(nombre='OTRO CONDUCTOR')
        self.fecha = date(2026, 7, 31)
        self.lote = Importacion.objects.create(nombre='reporte.xls', huella='a'*64, inicio=self.fecha, fin=self.fecha, creado_por=self.usuario)

    def salida(self, hora, uno=None, dos=None, lote=None, **kwargs):
        lote = lote or self.lote
        numero = lote.salidas.count()+1
        return Salida.objects.create(importacion=lote, fila=numero, fecha=self.fecha, hora=time(hora), bus='C0H-962', origen='Chiclayo', destino='Cajamarca',
            nombre_uno=(uno or self.a).nombre, nombre_dos=(dos or self.b).nombre, conductor_uno=uno or self.a, conductor_dos=dos or self.b, clave=f'{hora:064d}', **kwargs)

    def test_pendientes_no_suman_y_validar_es_idempotente(self):
        self.salida(7)
        self.assertEqual(calendario(self.fecha,self.fecha)[1], [])
        confirmar(self.lote.pk,self.usuario)
        confirmar(self.lote.pk,self.usuario)
        self.assertEqual(Salida.objects.count(),1)
        self.assertEqual(Auditoria.objects.count(),1)
        self.assertEqual(sum(f['trayectos'] for f in calendario(self.fecha,self.fecha)[1]),2)

    def test_tres_salidas_generan_xx_y_uno_y_medio(self):
        for h in (7,14,23): self.salida(h)
        confirmar(self.lote.pk,self.usuario)
        fila=next(f for f in calendario(self.fecha,self.fecha)[1] if f['conductor']==self.a)
        self.assertEqual(fila['celdas'][0]['etiqueta'],'XX')
        self.assertEqual(fila['vueltas'],1.5)

    def test_cambio_de_companero_y_posicion_cuenta_individual(self):
        self.salida(7)
        self.salida(14,uno=self.c,dos=self.a)
        confirmar(self.lote.pk,self.usuario)
        filas={f['conductor'].pk:f for f in calendario(self.fecha,self.fecha)[1]}
        self.assertEqual(filas[self.a.pk]['trayectos'],2)
        self.assertEqual(filas[self.a.pk]['celdas'][0]['etiqueta'],'X')
        self.assertEqual(filas[self.b.pk]['trayectos'],1)
        self.assertEqual(filas[self.c.pk]['trayectos'],1)

    def test_anulados_no_suman(self):
        self.salida(7); self.salida(14,anulado=True)
        confirmar(self.lote.pk,self.usuario)
        self.assertEqual(sum(f['trayectos'] for f in calendario(self.fecha,self.fecha)[1]),2)

    def test_bloquea_identidad_incompleta_o_repetida(self):
        s=self.salida(7); s.conductor_dos=None; s.save()
        with self.assertRaises(ValueError): confirmar(self.lote.pk,self.usuario)
        s.conductor_dos=self.a; s.save()
        with self.assertRaises(ValueError): confirmar(self.lote.pk,self.usuario)

    def test_bloquea_duplicado_entre_reportes(self):
        self.salida(7); confirmar(self.lote.pk,self.usuario)
        otro=Importacion.objects.create(nombre='otro.xls',huella='b'*64,inicio=self.fecha,fin=self.fecha,creado_por=self.usuario)
        self.salida(7,lote=otro)
        with self.assertRaises(ValueError): confirmar(otro.pk,self.usuario)
        otro.refresh_from_db(); self.assertEqual(otro.estado,'PENDIENTE')

    def test_dia_sin_viajes_es_pendiente_no_descanso(self):
        self.salida(7,original={'10':'0','12':'0'});confirmar(self.lote.pk,self.usuario)
        fila=next(f for f in calendario(self.fecha,self.fecha)[1] if f['conductor']==self.a)
        self.assertEqual(fila['descansos'],0)
        self.assertEqual(fila['pendientes'],1)

    def test_vacaciones_con_viajes_muestra_conflicto_y_anulacion_auditada(self):
        self.salida(7); confirmar(self.lote.pk,self.usuario)
        s=registrar_situacion(self.a,self.fecha,self.fecha,'VACACIONES','Vacaciones autorizadas',self.usuario)
        fila=next(f for f in calendario(self.fecha,self.fecha)[1] if f['conductor']==self.a)
        self.assertEqual(fila['conflictos'],1)
        self.assertEqual(fila['vacaciones'],1)
        self.client.post(reverse('conductores_anular_situacion',args=[s.pk]))
        s.refresh_from_db(); self.assertFalse(s.activa)
        self.assertEqual(s.auditoria_set.count(),2)

    def test_no_admite_situaciones_superpuestas(self):
        registrar_situacion(self.a,self.fecha,self.fecha,'DESCANSO','Programado',self.usuario)
        with self.assertRaises(ValueError): registrar_situacion(self.a,self.fecha,self.fecha,'VACACIONES','Otro',self.usuario)
        with self.assertRaises(ValueError): registrar_situacion(self.a,date(2026,8,1),self.fecha,'DESCANSO','Otro',self.usuario)

    def test_parser_encabezado_original_y_anulados(self):
        encabezado=['Fecha ',' Hora ',' Día ',' Bus ',' Origen ',' Destino ',' Conductor Nº1 ',' Conductor Nº2 ']
        filas,errores=interpretar_filas([['REPORTE'],encabezado,['2026/07/31','7:00 am','VIERNES','C0H-962','Chiclayo','Cajamarca',self.a.nombre,self.b.nombre],['2026/07/31','11:30 am','VIERNES','C0H-962','Chiclayo','Cajamarca','','','ANULADO'],['TOTAL']])
        self.assertFalse(errores)
        self.assertEqual(filas[0]['nombre_uno'],self.a.nombre)
        self.assertEqual(filas[0]['hora'],time(7))
        self.assertTrue(filas[1]['anulado'])

    def test_fila_malformada_genera_incidencia(self):
        filas,errores=interpretar_filas([['Fecha','Hora','Bus','Origen','Destino'],['2026/07/31','7:00 am','BUS','Chiclayo','Cajamarca'],['2026/07/31','hora mala','BUS','Chiclayo','Cajamarca']])
        self.assertEqual(len(errores),1)

    def test_nombre_en_orden_diferente_y_vinculacion(self):
        self.assertEqual(identidad('QUISPE SAAVEDRA ELBER'),identidad(self.a.nombre))
        s=self.salida(7); s.conductor_uno=None; s.save()
        self.client.post(reverse('conductores_detalle',args=[self.lote.pk]),{'accion':'vincular','nombre':self.a.nombre,'conductor':self.a.pk})
        s.refresh_from_db(); self.assertEqual(s.conductor_uno,self.a)
        self.assertTrue(IdentidadConductor.objects.exists())

    def test_pantallas_comparten_menu_y_detalle(self):
        self.salida(7)
        for name in ('conductores_importar','conductores_validacion','conductores_control','conductores_catalogo'):
            response=self.client.get(reverse(name),follow=True)
            self.assertContains(response,'Gestión bancaria')
            self.assertContains(response,'Gestión de conductores')
        self.assertContains(self.client.get(reverse('conductores_detalle',args=[self.lote.pk])),'Salidas del reporte')

    def test_control_periodo_invalido_y_popup(self):
        self.assertContains(self.client.get(reverse('conductores_control'),{'desde':'2026-08-31','hasta':'2026-08-01'}),'Seleccione un período')
        self.salida(7); confirmar(self.lote.pk,self.usuario)
        response=self.client.get(reverse('conductores_control'))
        self.assertContains(response,'detalle-dia-dialog')
        self.assertContains(response,'value="2026-07-31"')

    def test_sin_permiso_no_puede_mutar(self):
        self.usuario.rol='CONDUCTOR'; self.usuario.save()
        for name in ('conductores_importar','conductores_validacion','conductores_control','conductores_catalogo'):
            self.assertEqual(self.client.get(reverse(name)).status_code,403)
        self.assertEqual(self.client.post(reverse('conductores_detalle',args=[self.lote.pk]),{'accion':'confirmar'}).status_code,403)

    def test_importar_y_detectar_mismo_archivo(self):
        filas,_=interpretar_filas([['Fecha','Hora','Bus','Origen','Destino','Conductor Nº1','Conductor Nº2'],['2026/07/31','7:00 am','C0H-962','Chiclayo','Cajamarca',self.a.nombre,self.b.nombre]])
        with TemporaryDirectory() as carpeta, patch.object(Importacion._meta.get_field('archivo').storage, 'location', carpeta), patch('conductores.views.extraer',return_value=(filas,[])):
            for _ in range(2):
                response=self.client.post(reverse('conductores_importar'),{'archivo':SimpleUploadedFile('reporte.xls',b'archivo_prueba')})
                self.assertEqual(response.status_code,302)
        self.assertEqual(Importacion.objects.count(),2)
        self.assertEqual(Salida.objects.count(),1)

    def test_lectura_xlsx_real(self):
        from openpyxl import Workbook
        wb=Workbook(); ws=wb.active; ws.title='Reporte'
        ws.append(['Fecha','Hora','Bus','Origen','Destino','Conductor Nº1','Conductor Nº2'])
        ws.append([self.fecha,time(14,30),'C0H-962','Cajamarca','Chiclayo',self.a.nombre,self.b.nombre])
        b=BytesIO(); wb.save(b)
        filas,errores=extraer(SimpleUploadedFile('reporte.xlsx',b.getvalue()))
        self.assertFalse(errores); self.assertEqual(filas[0]['hora'],time(14,30))
