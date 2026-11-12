from datetime import date, time
from django.test import TestCase
from django.urls import reverse
from asistencia.models import Trabajador, TurnoHorario, ProgramacionHorario
from asistencia.services.grupos_horarios import agrupar_programacion
from core.models import Usuario


class GruposHorariosTests(TestCase):
    def test_agrupa_sin_mezclar_meses_turnos_o_trabajadores(self):
        actor = Usuario.objects.create_user('grupos', email='grupos@example.invalid', dni='11223344', rol='CONTADORA')
        trabajador = Trabajador.objects.create(nombre_completo='Prueba', dni='22334455', area='Ventas')
        otro = Trabajador.objects.create(nombre_completo='Otra persona', dni='33445566', area='Ventas')
        manana = TurnoHorario.objects.create(nombre='Mañana', hora_entrada=time(6), hora_salida=time(14,30))
        noche = TurnoHorario.objects.create(nombre='Noche', hora_entrada=time(20), hora_salida=time(7))
        for t, turno, fecha in [(trabajador,manana,date(2026,11,2)), (trabajador,manana,date(2026,11,4)), (trabajador,noche,date(2026,11,5)), (trabajador,manana,date(2026,12,1)), (otro,manana,date(2026,11,2))]:
            ProgramacionHorario.objects.create(trabajador=t, turno=turno, fecha=fecha, responsable=actor, motivo='Prueba')
        grupos = agrupar_programacion(ProgramacionHorario.objects.select_related('trabajador','turno'))
        self.assertEqual(len(grupos),4)
        grupo = next(g for g in grupos if g['trabajador']==trabajador and g['mes']==date(2026,11,1) and g['turno']==manana)
        self.assertEqual(grupo['total'],2)
        self.assertEqual(grupo['dias'],'Lunes, Miércoles')
        self.assertEqual([p.fecha.day for p in grupo['fechas']],[2,4])
        self.client.force_login(actor)
        respuesta = self.client.get(reverse('programar_horarios'), {'desde':'2026-11-01','hasta':'2026-12-31','trabajador':trabajador.pk})
        self.assertEqual(respuesta.status_code,200)
        self.assertEqual(respuesta.context['programacion'].paginator.count,3)
        self.assertContains(respuesta,'Fechas configuradas')
        self.assertContains(respuesta,'2 días')
        respuesta = self.client.get(reverse('programar_horarios'), {'desde':'2026-11-01','hasta':'2026-11-30','trabajador':trabajador.pk})
        self.assertEqual(respuesta.context['programacion'].paginator.count,3)
        self.assertContains(respuesta,'id="buscar-horario"')
        self.assertContains(respuesta,'Diciembre 2026')
        respuesta = self.client.get(reverse('programar_horarios'), {'buscar_horario':'22334455'})
        self.assertEqual(respuesta.context['programacion'].paginator.count,3)
        respuesta = self.client.get(reverse('programar_horarios'), {'buscar_horario':'nadie-con-este-nombre'})
        self.assertEqual(respuesta.context['programacion'].paginator.count,0)
