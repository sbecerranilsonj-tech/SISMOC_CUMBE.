"""Resolución explícita de trabajo en un descanso previsto, sin aprobar ni pagar automáticamente."""
from datetime import date
from django.core.exceptions import ValidationError
from django.db import transaction
from asistencia.models import Trabajador, ResumenAsistenciaDiaria, DescansoProgramado, MarcacionBiometrica
from asistencia.services.reglas_jornada import programacion_descanso
from asistencia.services.revision import comprobar_abierto, detalle_jornada, puede_aprobar, registrar_historial, marcas_persona


@transaction.atomic
def confirmar_descanso_trabajado(resumen, tipo, destino, actor):
    if not puede_aprobar(actor):
        raise ValidationError('La confirmación corresponde a Contabilidad o Gerencia.')
    if not resumen.trabajador_id:
        raise ValidationError('Vincule primero la ficha del trabajador.')
    Trabajador.objects.select_for_update().get(pk=resumen.trabajador_id)
    resumen = ResumenAsistenciaDiaria.objects.select_for_update().get(pk=resumen.pk)
    comprobar_abierto(resumen.fecha)
    if resumen.verificado_contabilidad:
        raise ValidationError('Reabra la jornada antes de cambiar esta situación.')
    regla = programacion_descanso(resumen)
    detalle = detalle_jornada(resumen, incluir_formulario=False)
    if not regla or not any(m.es_valida for m in detalle['marcas']):
        raise ValidationError('La jornada debe tener marcaciones en un descanso programado.')
    if tipo not in {'DESCANSO_TRABAJADO', 'CAMBIO_DESCANSO'}:
        raise ValidationError('Seleccione descanso trabajado o cambio de descanso.')
    anterior = resumen.conceptos_editados.get('situacion_descanso', {})
    nueva_fecha = None
    if tipo == 'CAMBIO_DESCANSO':
        try:
            nueva_fecha = date.fromisoformat(destino or '')
        except ValueError:
            raise ValidationError('Indique la nueva fecha de descanso.')
        if nueva_fecha == resumen.fecha or abs((nueva_fecha - resumen.fecha).days) > 366:
            raise ValidationError('Elija otra fecha de descanso, a un máximo de 366 días.')
        comprobar_abierto(nueva_fecha)
        dias_destino = ResumenAsistenciaDiaria.objects.filter(trabajador_id=resumen.trabajador_id, fecha=nueva_fecha)
        if dias_destino.filter(verificado_contabilidad=True).exists():
            raise ValidationError('La fecha de destino ya está aprobada. Reábrala antes de trasladar el descanso.')
        for dia in dias_destino:
            if any(m.es_valida for m in detalle_jornada(dia, incluir_formulario=False)['marcas']):
                raise ValidationError('La nueva fecha tiene marcaciones. Seleccione un día sin trabajo registrado.')
        if MarcacionBiometrica.objects.filter(marcas_persona(resumen), fecha_hora__date=nueva_fecha, es_valida=True).exists():
            raise ValidationError('La nueva fecha tiene marcaciones. Revísela antes de trasladar el descanso.')
    if anterior.get('tipo') == tipo and anterior.get('fecha_destino') == (nueva_fecha.isoformat() if nueva_fecha else None) and anterior.get('programacion_id') == regla.pk:
        return
    previo_id = anterior.get('descanso_destino_id')
    if previo_id:
        previo = DescansoProgramado.objects.filter(pk=previo_id, trabajador_id=resumen.trabajador_id).first()
        if previo:
            comprobar_abierto(previo.desde)
            if ResumenAsistenciaDiaria.objects.filter(trabajador_id=resumen.trabajador_id, fecha=previo.desde, verificado_contabilidad=True).exists():
                raise ValidationError('Reabra el día de descanso anterior antes de cambiar su traslado.')
            previo.delete()
    programado = None
    if nueva_fecha:
        programado = DescansoProgramado.objects.create(trabajador_id=resumen.trabajador_id, desde=nueva_fecha, hasta=nueva_fecha, dias=[nueva_fecha.weekday()], responsable=actor)
    decision = {'tipo': tipo, 'fecha_destino': nueva_fecha.isoformat() if nueva_fecha else None,
                'programacion_id': regla.pk, 'descanso_destino_id': programado.pk if programado else None}
    resumen.conceptos_editados = {**resumen.conceptos_editados, 'situacion_descanso': decision}
    resumen.save(update_fields=['conceptos_editados'])
    registrar_historial(resumen, actor, 'Trabajo en descanso confirmado', f'Antes: {anterior}. Ahora: {decision}. No genera aprobación ni horas adicionales automáticas.')
