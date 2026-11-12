from django.db import transaction
from django.core.exceptions import ValidationError
from asistencia.models import Trabajador, ResumenAsistenciaDiaria, CierreAsistencia
from asistencia.services.revision import puede_aprobar, registrar_historial
from asistencia.services.reglas_jornada import solo_horas_trabajadas
from asistencia.services.revision_trabajador import validar_periodo

@transaction.atomic
def configurar_solo_horas(trabajador, activo, actor):
    if not puede_aprobar(actor):
        raise ValidationError('La configuración corresponde a Contabilidad o Gerencia.')
    trabajador = Trabajador.objects.select_for_update().get(pk=trabajador.pk)
    jornadas = list(ResumenAsistenciaDiaria.objects.select_for_update(of=('self',)).filter(trabajador=trabajador))
    cierres = list(CierreAsistencia.objects.all())
    abiertas = []
    for r in jornadas:
        if r.verificado_contabilidad or any(c.fecha_inicio <= r.fecha <= c.fecha_fin for c in cierres):
            r.conceptos_editados.setdefault('solo_horas_trabajadas', solo_horas_trabajadas(r))
            r.save(update_fields=['conceptos_editados'])
        else:
            r.conceptos_editados.pop('solo_horas_trabajadas', None)
            r.save(update_fields=['conceptos_editados'])
            abiertas.append(r)
    trabajador.solo_horas_trabajadas = activo
    trabajador.save(update_fields=['solo_horas_trabajadas'])
    for r in abiertas:
        r.trabajador = trabajador
        validar_periodo([r], {}, {}, None, 'Modalidad de horas trabajadas actualizada.', actor)
    registrar_historial(None, actor, 'Modalidad de horas trabajadas', f'Trabajador #{trabajador.pk}: solo horas={activo}. Aprobadas y cerradas conservadas.')



@transaction.atomic
def configurar_extras(trabajador, extras25, extras35, actor):
    if not puede_aprobar(actor):
        raise ValidationError('La configuración corresponde a Contabilidad o Gerencia.')
    trabajador = Trabajador.objects.select_for_update().get(pk=trabajador.pk)
    from asistencia.services.reglas_jornada import calcular_extra
    jornadas = list(ResumenAsistenciaDiaria.objects.select_for_update(of=('self',)).filter(trabajador=trabajador))
    cierres = list(CierreAsistencia.objects.all())
    abiertas = []
    for r in jornadas:
        if r.verificado_contabilidad or any(c.fecha_inicio <= r.fecha <= c.fecha_fin for c in cierres):
            for porcentaje in (25, 35):
                r.conceptos_editados.setdefault(f'calcular_extras_{porcentaje}', calcular_extra(r, porcentaje))
        else:
            for porcentaje in (25, 35):
                r.conceptos_editados.pop(f'calcular_extras_{porcentaje}', None)
            abiertas.append(r)
        r.save(update_fields=['conceptos_editados'])
    trabajador.calcular_extras_25 = extras25
    trabajador.calcular_extras_35 = extras35
    trabajador.save(update_fields=['calcular_extras_25', 'calcular_extras_35'])
    for r in abiertas:
        r.trabajador = trabajador
        validar_periodo([r], {}, {}, None, 'Configuración de horas extras actualizada.', actor)
    registrar_historial(None, actor, 'Configuración de extras', f'Trabajador #{trabajador.pk}: 25%={extras25}; 35%={extras35}.')
