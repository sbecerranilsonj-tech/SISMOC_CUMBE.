from datetime import date,datetime,time
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from asistencia.models import CargaArchivoAsistencia, FilaImportacionBiometrica, MarcacionBiometrica, IdentidadBiometrica, Trabajador, ResumenAsistenciaDiaria
from asistencia.services.grupos_importacion import grupo_importacion
from asistencia.services.revision import detalle_jornada
from core.models import Usuario


class GruposImportacionTests(TestCase):
    def test_todos_los_registros_incluye_y_envia_varios_meses(self):
        from asistencia.services.grupos_importacion import validar_grupo_envio
        from django.core.exceptions import ValidationError
        grupo = grupo_importacion({'grupo_mes':'todos'})
        self.assertTrue(grupo['todos'])
        self.assertIsNone(grupo['inicio'])
        self.assertEqual(set(grupo['marcas'].values_list('pk',flat=True)),{self.agosto.pk,self.septiembre.pk})
        self.assertEqual(set(grupo['cargas'].values_list('pk',flat=True)),{self.a.pk,self.b.pk})
        validar_grupo_envio({'grupo_mes':'todos'},date(2026,8,1),date(2026,9,30))
        respuesta=self.client.get(reverse('dashboard'),{'vista':'excel-zk','grupo_mes':'todos'})
        self.assertContains(respuesta,'Todos los registros')
        self.assertContains(respuesta,'Todos los archivos')
        repetida=self.marca(self.a,date(2026,8,1),9)
        repetida.fecha_hora=self.agosto.fecha_hora.replace(second=2)
        repetida.save()
        respuesta=self.client.post(reverse('enviar_a_asistencia'),{'grupo_mes':'todos',
            'desde_envio':'2026-08-01','hasta_envio':'2026-09-30','confirmar_identificacion':'si'})
        self.assertEqual(respuesta.status_code,302)
        self.assertEqual(set(ResumenAsistenciaDiaria.objects.values_list('fecha',flat=True)),{date(2026,8,1),date(2026,9,1)})
        agosto=ResumenAsistenciaDiaria.objects.get(fecha=date(2026,8,1))
        self.assertEqual(set(agosto.marcaciones_publicadas),{self.agosto.pk,repetida.pk})
        self.assertFalse(agosto.verificado_contabilidad)

    def test_filtro_pendientes_muestra_solo_codigos_sin_ficha(self):
        pendiente=IdentidadBiometrica.objects.create(sede='CAJAMARCA',equipo='1',codigo='43',nombre='Sin ficha')
        MarcacionBiometrica.objects.create(identidad_biometrica=pendiente,carga_origen=self.a,
            fecha_hora=timezone.make_aware(datetime(2026,8,2,8)),origen='EXCEL_ZKTECO')
        filtros={'vista':'excel-zk','grupo_mes':'2026-08','grupo_carga':self.a.pk,'sede_codigo':'CAJAMARCA','identificacion':'pendientes'}
        res=self.client.get(reverse('dashboard'),filtros)
        self.assertEqual([i.pk for i in res.context['identidades_biometricas']],[pendiente.pk])
        self.assertEqual([(f['estado'],f['total']) for f in res.context['enlaces_identificacion']],[('todos',2),('pendientes',1),('identificados',1)])
        res=self.client.get(reverse('dashboard'),{**filtros,'identificacion':'identificados'})
        self.assertEqual([i.pk for i in res.context['identidades_biometricas']],[self.identidad.pk])
        sugerencias=self.client.get(reverse('sugerir_codigos'),{**filtros,'q':'4'}).json()
        self.assertEqual([i['codigo'] for i in sugerencias['resultados']],['43'])

    def test_sugerencias_codigo_respetan_archivo_mes_y_sede(self):
        otra = IdentidadBiometrica.objects.create(sede='CHICLAYO', equipo='104', codigo='42001', nombre='Persona Otra')
        MarcacionBiometrica.objects.create(identidad_biometrica=otra, carga_origen=self.b,
            fecha_hora=timezone.make_aware(datetime(2026,9,2,8)), origen='EXCEL_ZKTECO')
        url = reverse('sugerir_codigos')
        filtros = {'q':'4','grupo_mes':'2026-08','grupo_carga':self.a.pk,'sede_codigo':'CAJAMARCA'}
        respuesta = self.client.get(url, filtros)
        self.assertEqual(respuesta.status_code,200)
        self.assertEqual([i['codigo'] for i in respuesta.json()['resultados']],['42'])
        respuesta = self.client.get(url, {**filtros,'grupo_mes':'2026-09','grupo_carga':self.b.pk,'sede_codigo':'CHICLAYO'})
        self.assertEqual([i['codigo'] for i in respuesta.json()['resultados']],['42001'])
        self.assertEqual(self.client.get(url, {**filtros,'grupo_carga':'invalido'}).json()['resultados'],[])
        self.assertEqual(self.client.get(url, {'q':''}).json()['resultados'],[])
        self.actor.rol='ADMINISTRATIVO'
        self.actor.save()
        self.assertEqual(self.client.get(url,filtros).status_code,403)

    def setUp(self):
        self.actor=Usuario.objects.create_user('grupos',email='grupos@example.invalid',dni='11111111',rol='CONTADORA')
        self.ficha=Trabajador.objects.create(nombre_completo='Persona Grupos',dni='22222222',area='Boletería',sede='CAJAMARCA')
        self.identidad=IdentidadBiometrica.objects.create(sede='CAJAMARCA',equipo='1',codigo='42',trabajador=self.ficha)
        self.a=CargaArchivoAsistencia.objects.create(nombre_archivo_original='Agosto.xlsx',mes_periodo='2026-08',subido_por=self.actor)
        self.b=CargaArchivoAsistencia.objects.create(nombre_archivo_original='Septiembre.xlsx',mes_periodo='2026-09',subido_por=self.actor)
        self.client.force_login(self.actor)
        self.agosto=self.marca(self.a,date(2026,8,1),8)
        self.septiembre=self.marca(self.b,date(2026,9,1),8)

    def marca(self,carga,dia,hora):
        m=MarcacionBiometrica.objects.create(identidad_biometrica=self.identidad,fecha_hora=timezone.make_aware(datetime.combine(dia,time(hora))),carga_origen=carga,origen='EXCEL_ZKTECO',tipo_evento='SIN_CLASIFICAR')
        FilaImportacionBiometrica.objects.create(carga=carga,marcacion=m,identidad=self.identidad,hoja='CAJAMARCA',fila=carga.filas_origen.count()+2)
        return m

    def test_grupos_por_fecha_real_y_no_por_mes_dominante_de_archivo(self):
        self.marca(self.a,date(2026,7,31),17)
        g=grupo_importacion({'grupo_carga':str(self.a.pk)})
        self.assertEqual(g['mes'],'2026-08')
        self.assertEqual({m['valor'] for m in g['meses']},{'2026-07','2026-08','2026-09'})
        self.assertEqual(list(g['marcas'].values_list('pk',flat=True)),[self.agosto.pk])

    def test_archivos_del_mismo_mes_no_mezclan_marcas_en_detalle(self):
        otro=CargaArchivoAsistencia.objects.create(nombre_archivo_original='Corrección agosto.xlsx',mes_periodo='2026-08')
        interna=self.marca(otro,date(2026,8,1),12)
        data={'confirmar_identificacion':'si','desde_envio':'2026-08-01','hasta_envio':'2026-08-01','grupo_mes':'2026-08','grupo_carga':self.a.pk}
        self.assertEqual(self.client.post(reverse('enviar_a_asistencia'),data).status_code,302)
        r=ResumenAsistenciaDiaria.objects.get()
        self.assertEqual(r.marcaciones_publicadas,[self.agosto.pk])
        self.assertNotIn(interna.pk,[m.pk for m in detalle_jornada(r)['marcas']])
        self.assertEqual(r.fecha,date(2026,8,1))

    def test_rango_fuera_del_mes_se_rechaza_sin_publicar(self):
        data={'confirmar_identificacion':'si','desde_envio':'2026-08-01','hasta_envio':'2026-09-01','grupo_mes':'2026-08','grupo_carga':self.a.pk}
        self.client.post(reverse('enviar_a_asistencia'),data)
        self.assertFalse(ResumenAsistenciaDiaria.objects.exists())

    def test_ui_consulta_y_detalle_solo_del_grupo(self):
        q={'vista':'excel-zk','grupo_mes':'2026-08','grupo_carga':str(self.a.pk),'codigo_biometrico':self.identidad.pk}
        res=self.client.get(reverse('dashboard'),q)
        self.assertEqual(res.status_code,200)
        self.assertEqual([m.pk for m in res.context['marcas_codigo']],[self.agosto.pk])
        self.assertEqual(res.context['desde_envio'],'2026-08-01')
        self.assertEqual(res.context['hasta_envio'],'2026-08-01')
        self.assertContains(res,'Agosto 2026')
        self.assertContains(res,'Archivo cargado')

    def test_repetidas_tienen_procedencia_en_ambas_cargas_sin_duplicar_grupo(self):
        FilaImportacionBiometrica.objects.create(carga=self.b,marcacion=self.agosto,identidad=self.identidad,hoja='CAJAMARCA',fila=99,repetida=True)
        g=grupo_importacion({'grupo_mes':'2026-08','grupo_carga':str(self.b.pk)})
        self.assertEqual(g['marcas'].count(),1)
        self.assertEqual({c.pk for c in g['cargas']},{self.a.pk,self.b.pk})

    def test_archivo_invalido_no_retorna_todos_los_datos(self):
        g=grupo_importacion({'grupo_mes':'2026-08','grupo_carga':'no-valido'})
        self.assertTrue(g['error'])
        self.assertFalse(g['marcas'].exists())

    def test_otro_mes_no_aparece_en_lista_de_identidades(self):
        p=Trabajador.objects.create(nombre_completo='Otra Persona',dni='33333333',area='Operaciones',sede='JAEN')
        i=IdentidadBiometrica.objects.create(sede='JAEN',equipo='1',codigo='55',trabajador=p)
        m=MarcacionBiometrica.objects.create(identidad_biometrica=i,fecha_hora=timezone.make_aware(datetime(2026,9,2,8)),carga_origen=self.b)
        FilaImportacionBiometrica.objects.create(carga=self.b,marcacion=m,identidad=i,hoja='JAEN',fila=100)
        res=self.client.get(reverse('dashboard'),{'vista':'excel-zk','grupo_mes':'2026-08'})
        self.assertEqual(res.context['total_codigos_filtrados'],1)
        self.assertNotIn(i,list(res.context['identidades_biometricas']))

    def test_marcacion_manual_completa_el_grupo_sin_incluir_otro_archivo(self):
        from asistencia.services.transferencia import pasar_a_asistencia
        from asistencia.services.marcacion_manual import agregar_marcacion_manual
        externa=self.marca(self.b,date(2026,8,1),12)
        pasar_a_asistencia([self.ficha.pk],date(2026,8,1),date(2026,8,1),self.actor,marcas_ids=[self.agosto.pk])
        r=ResumenAsistenciaDiaria.objects.get()
        m=agregar_marcacion_manual(r,{'fecha_manual':'2026-08-01','hora_manual':'17:00','tipo_evento_manual':'SALIDA','motivo_manual':'Salida confirmada'},self.actor)
        r.refresh_from_db()
        self.assertIn(m.pk,r.marcaciones_publicadas)
        self.assertNotIn(externa.pk,[marca.pk for marca in detalle_jornada(r)['marcas']])

    def test_nocturna_de_fin_de_mes_incluye_solo_su_salida_del_siguiente(self):
        from asistencia.models import TurnoHorario
        from asistencia.services.horarios import programar_horarios
        noche=TurnoHorario.objects.create(nombre='Noche',hora_entrada=time(20),hora_salida=time(6))
        programar_horarios(self.ficha,date(2026,8,31),date(2026,8,31),[0],noche,'Turno confirmado',self.actor)
        entrada=self.marca(self.a,date(2026,8,31),20)
        salida=self.marca(self.a,date(2026,9,1),6)
        self.client.post(reverse('enviar_a_asistencia'),{'confirmar_identificacion':'si','desde_envio':'2026-08-31','hasta_envio':'2026-08-31','grupo_mes':'2026-08','grupo_carga':self.a.pk})
        r=ResumenAsistenciaDiaria.objects.get()
        self.assertEqual(r.fecha,date(2026,8,31))
        self.assertEqual(set(r.marcaciones_publicadas),{entrada.pk,salida.pk})
