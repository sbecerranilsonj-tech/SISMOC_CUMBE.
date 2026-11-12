"""Asignación de vacaciones por rango y validación contable conjunta."""
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from asistencia.models import Trabajador, PeriodoVacaciones, ResumenAsistenciaDiaria, IncidenciaAsistencia, MarcacionBiometrica
from asistencia.services.revision import puede_aprobar, comprobar_abierto, detalle_jornada, registrar_historial, marcas_persona


def dias_periodo(desde, hasta):
    return [desde + timedelta(days=i) for i in range((hasta-desde).days+1)]


def comprobar_sin_trabajo(r):
    comprobar_abierto(r.fecha)
    if any(m.es_valida for m in detalle_jornada(r, incluir_formulario=False)['marcas']) or r.ajustes.exists() or r.horas_trabajadas:
        raise ValidationError(f'{r.fecha:%d/%m/%Y}: tiene marcaciones, horas o ajustes. Revise ese día antes de asignar vacaciones.')
    if MarcacionBiometrica.objects.filter(marcas_persona(r), fecha_hora__date=r.fecha, es_valida=True).exists():
        raise ValidationError(f'{r.fecha:%d/%m/%Y}: hay marcaciones de origen. Revise ese día antes de validar vacaciones.')


@transaction.atomic
def asignar_vacaciones(trabajador, desde, hasta, actor):
    if not puede_aprobar(actor):
        raise ValidationError('Solo Contabilidad o Gerencia puede asignar vacaciones.')
    if not 0 <= (hasta-desde).days <= 365:
        raise ValidationError('Seleccione un periodo válido de hasta 366 días.')
    Trabajador.objects.select_for_update().get(pk=trabajador.pk)
    if PeriodoVacaciones.objects.filter(trabajador=trabajador, desde__lte=hasta, hasta__gte=desde).exists():
        raise ValidationError('El rango coincide con vacaciones ya asignadas.')
    periodo = PeriodoVacaciones.objects.create(trabajador=trabajador, desde=desde, hasta=hasta, creado_por=actor)
    for fecha in dias_periodo(desde,hasta):
        comprobar_abierto(fecha)
        r, _ = ResumenAsistenciaDiaria.objects.get_or_create(trabajador=trabajador, fecha=fecha, defaults={'estado':'VACACIONES', 'marcaciones_publicadas':[]})
        comprobar_sin_trabajo(r)
        if r.verificado_contabilidad or r.incidencias.exists():
            raise ValidationError(f'{fecha:%d/%m/%Y}: ya tiene una aprobación o situación registrada. Revísela antes de asignar vacaciones.')
        r.estado='VACACIONES';r.save(update_fields=['estado'])
        IncidenciaAsistencia.objects.create(resumen=r, tipo='VACACIONES', motivo=f'Vacaciones asignadas del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}.', creado_por=actor)
    registrar_historial(None,actor,'Vacaciones asignadas',f'Trabajador #{trabajador.pk}: periodo #{periodo.pk}; {desde} al {hasta}. Pendiente de validación conjunta.')
    return periodo


@transaction.atomic
def validar_vacaciones(periodo, actor):
    if not puede_aprobar(actor):
        raise ValidationError('Solo Contabilidad o Gerencia puede validar las vacaciones.')
    Trabajador.objects.select_for_update().get(pk=periodo.trabajador_id)
    periodo=PeriodoVacaciones.objects.select_for_update().get(pk=periodo.pk)
    from asistencia.services.aprobacion_situacion import aprobar_situacion_del_dia
    for fecha in dias_periodo(periodo.desde,periodo.hasta):
        r=ResumenAsistenciaDiaria.objects.select_for_update(of=("self",)).filter(trabajador_id=periodo.trabajador_id,fecha=fecha).first()
        if not r:
            raise ValidationError(f'{fecha:%d/%m/%Y}: falta la jornada del periodo asignado.')
        comprobar_sin_trabajo(r)
        incidencias=list(r.incidencias.all())
        if len(incidencias)!=1 or incidencias[0].tipo!='VACACIONES':
            raise ValidationError(f'{fecha:%d/%m/%Y}: la situación fue modificada. Revísela antes de validar el periodo.')
        if r.verificado_contabilidad:
            if r.estado!='VACACIONES' or not incidencias[0].aprobado_el:
                raise ValidationError(f'{fecha:%d/%m/%Y}: la aprobación no corresponde a vacaciones.')
        else:
            aprobar_situacion_del_dia(r,actor,'VACACIONES')
    periodo.aprobado_por=actor;periodo.aprobado_el=timezone.now();periodo.save(update_fields=['aprobado_por','aprobado_el'])
    registrar_historial(None,actor,'Vacaciones validadas',f'Trabajador #{periodo.trabajador_id}: periodo #{periodo.pk}; {periodo.desde} al {periodo.hasta}, {periodo.total_dias} días.')

