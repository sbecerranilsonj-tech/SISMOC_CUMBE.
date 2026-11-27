from datetime import date, datetime, time
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.models import Usuario
from asistencia.models import Trabajador, IdentidadBiometrica, MarcacionBiometrica, ResumenAsistenciaDiaria
from asistencia.services.transferencia import pasar_a_asistencia
from asistencia.services.unificar_trabajadores import unificar_trabajadores
from asistencia.services.revision import detalle_jornada
from asistencia.services.revision_trabajador import validar_periodo


class UnificarTrabajadoresTests(TestCase):
    def test_codigo_compartido_bloquea_y_union_conserva_cuatro_marcas(self):
        actor = Usuario.objects.create_user('contadora_union', email='union@example.invalid', dni='11223344', rol='CONTADORA')
        a = Trabajador.objects.create(nombre_completo='Carlos Arteaga', dni='12345663', area='Trabajo', sede='CHICLAYO')
        b = Trabajador.objects.create(nombre_completo='Carlos Arteaga', dni='12345664', area='Trabajo', sede='CHICLAYO')
        dia = date(2026,8,1)
        ids = []
        for ficha, equipo, horas in [(a,'104',[8,17]), (b,'1',[12,13])]:
            identidad = IdentidadBiometrica.objects.create(codigo='42406447', equipo=equipo, sede='CHICLAYO', trabajador=ficha)
            marcas = [MarcacionBiometrica.objects.create(identidad_biometrica=identidad, fecha_hora=timezone.make_aware(datetime.combine(dia,time(h))), tipo_evento='SIN_CLASIFICAR') for h in horas]
            ids.extend(m.pk for m in marcas)
            ResumenAsistenciaDiaria.objects.create(trabajador=ficha, fecha=dia, primera_entrada=time(min(horas)), ultima_salida=time(max(horas)), marcaciones_publicadas=[m.pk for m in marcas])
        with self.assertRaises(ValidationError):
            pasar_a_asistencia([a.pk,b.pk], dia,dia,actor)
        with self.assertRaises(ValidationError):
            pasar_a_asistencia([a.pk], dia,dia,actor)
        self.assertEqual(unificar_trabajadores(a.pk,b.pk,actor),1)
        self.assertEqual(Trabajador.objects.filter(pk=b.pk).count(),0)
        r = ResumenAsistenciaDiaria.objects.get(trabajador=a)
        self.assertEqual(set(r.marcaciones_publicadas),set(ids))
        self.assertEqual(len(detalle_jornada(r)['marcas']),4)
        cambios = dict(zip([m.pk for m in MarcacionBiometrica.objects.order_by('fecha_hora')],['ENTRADA','SALIDA_REFRIGERIO','RETORNO_REFRIGERIO','SALIDA']))
        from django.db import transaction
        with transaction.atomic():
            validar_periodo([r],cambios,{pk:'SIN_CLASIFICAR' for pk in ids},None,'Revisión',actor)
        r.refresh_from_db()
        self.assertTrue(detalle_jornada(r)['completa'])
        self.assertEqual(detalle_jornada(r)['bloqueos'],[])
        from asistencia.services.revision import revisar
        revisar(r, actor, 'APROBADO')
        self.assertTrue(r.verificado_contabilidad)
        from django.urls import reverse
        self.client.force_login(actor)
        respuesta = self.client.post(reverse('cerrar_periodo'), {'desde': str(dia), 'hasta': str(dia), 'confirmar': 'si'})
        self.assertEqual(respuesta.status_code, 302)
        from asistencia.models import CierreAsistencia
        self.assertTrue(CierreAsistencia.objects.filter(fecha_inicio=dia,fecha_fin=dia).exists())
