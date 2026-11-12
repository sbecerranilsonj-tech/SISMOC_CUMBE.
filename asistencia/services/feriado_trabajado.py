"""Confirmación contable de ocho horas adicionales por feriado trabajado."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from asistencia.models import AjusteAsistencia, ResumenAsistenciaDiaria
from asistencia.services.reglas_jornada import calendario_especial
from asistencia.services.revision import comprobar_abierto, detalle_jornada, puede_aprobar, registrar_historial


@transaction.atomic
def confirmar_feriado_trabajado(resumen, actor):
    if not puede_aprobar(actor):
        raise ValidationError('No tiene permiso para confirmar el feriado trabajado.')
    resumen = ResumenAsistenciaDiaria.objects.select_for_update().get(pk=resumen.pk)
    comprobar_abierto(resumen.fecha)
    if resumen.verificado_contabilidad:
        raise ValidationError('Reabra la jornada antes de confirmar el feriado trabajado.')
    if resumen.fecha not in calendario_especial(resumen.fecha, resumen.fecha):
        raise ValidationError('La fecha no está registrada como feriado o día especial.')
    if resumen.ajustes.filter(concepto='descanso_feriado').exists():
        raise ValidationError('Esta jornada ya tiene un registro de feriado o descanso. Revíselo antes de agregar otro.')
    detalle = detalle_jornada(resumen, incluir_formulario=False)
    if not detalle['completa'] or detalle['propuestas_eventos'] or detalle['falta_refrigerio']:
        raise ValidationError('Confirme y valide las marcaciones antes de registrar el feriado trabajado.')
    from asistencia.services.reglas_jornada import solo_horas_trabajadas, trabajo_efectivo
    from asistencia.services.cuadro_excel import formato_tiempo
    segundos = int(trabajo_efectivo(resumen, detalle['tramos'])) if solo_horas_trabajadas(resumen) else 28800
    if segundos <= 0:
        raise ValidationError('No hay tiempo trabajado para registrar el adicional.')
    texto = formato_tiempo(segundos)
    ajuste = AjusteAsistencia.objects.create(
        resumen=resumen, concepto='descanso_feriado', minutos=max(1, round(segundos / 60)),
        motivo=f'Feriado trabajado confirmado por Contabilidad: {texto} adicionales.',
        creado_por=actor, aprobado_por=actor, aprobado_el=timezone.now(),
    )
    if solo_horas_trabajadas(resumen):
        resumen.conceptos_editados.setdefault('feriado_segundos', {})[str(ajuste.pk)] = segundos
        resumen.save(update_fields=['conceptos_editados'])
    registrar_historial(resumen, actor, 'Feriado trabajado confirmado',
                        f'{texto} adicionales registradas por separado. La jornada conserva su revisión pendiente.')
    return ajuste
