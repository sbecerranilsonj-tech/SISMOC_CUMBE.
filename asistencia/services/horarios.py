"""Programación explícita, sin deducir el horario contractual de las marcas."""
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from asistencia.models import ProgramacionHorario, Trabajador, ResumenAsistenciaDiaria, CierreAsistencia
from asistencia.services.revision import puede_gestionar, comprobar_abierto, dejar_pendiente, registrar_historial, detalle_jornada


def turno_programado(trabajador, fecha):
    if not isinstance(trabajador, Trabajador):
        ficha = Trabajador.objects.filter(usuario=trabajador).first()
        if not ficha:
            return trabajador.turno
        trabajador = ficha
    p = ProgramacionHorario.objects.select_related('turno').filter(trabajador=trabajador, fecha=fecha).first()
    return p.turno if p else trabajador.turno


def actualizar_tardanza(resumen, detalle=None, *, guardar=True):
    detalle = detalle or detalle_jornada(resumen, incluir_formulario=False)
    if resumen.estado not in {'POR_REVISAR', 'ASISTIO', 'TARDANZA'}:
        return
    if detalle['turno'] and not detalle['turno'].evaluar_tardanzas:
        resumen.minutos_tardanza = 0
        resumen.estado = 'ASISTIO' if detalle['completa'] else 'POR_REVISAR'
    elif not detalle['turno'] or not detalle['completa']:
        resumen.minutos_tardanza = 0
        resumen.estado = 'POR_REVISAR'
    else:
        turno = detalle['turno']
        programada = timezone.make_aware(datetime.combine(resumen.fecha, turno.hora_entrada))
        atraso = max(0, (detalle['tramos'][0]['inicio'] - programada).total_seconds())
        resumen.minutos_tardanza = int(atraso // 60) if atraso > turno.tolerancia_minutos * 60 else 0
        resumen.estado = 'TARDANZA' if resumen.minutos_tardanza else 'ASISTIO'
    if guardar:
        resumen.save(update_fields=['estado', 'minutos_tardanza'])


@transaction.atomic
def programar_horarios(trabajador, desde, hasta, dias, turno, motivo, actor):
    if not puede_gestionar(actor):
        raise ValidationError('No tiene permiso para programar horarios.')
    if hasta < desde or (hasta - desde).days > 365:
        raise ValidationError('Seleccione un rango de hasta 366 días.')
    if not dias or not set(dias).issubset(set(range(7))):
        raise ValidationError('Seleccione los días de la semana.')
    if not turno.activo:
        raise ValidationError('Seleccione un turno activo.')
    Trabajador.objects.select_for_update().get(pk=trabajador.pk)
    fechas = [desde + timedelta(days=i) for i in range((hasta-desde).days+1) if (desde+timedelta(days=i)).weekday() in dias]
    if not fechas:
        raise ValidationError('Los días seleccionados no aparecen en ese rango.')
    if CierreAsistencia.objects.filter(fecha_inicio__lte=max(fechas), fecha_fin__gte=min(fechas)).exists():
        for fecha in fechas:
            comprobar_abierto(fecha)
    consulta = Q(trabajador=trabajador)
    if trabajador.usuario_id:
        consulta |= Q(trabajador__isnull=True, usuario_id=trabajador.usuario_id)
    jornadas = list(ResumenAsistenciaDiaria.objects.select_for_update().filter(consulta, fecha__in=fechas).order_by('fecha'))
    por_fecha = {r.fecha:r for r in jornadas}
    anteriores = {p.fecha:p for p in ProgramacionHorario.objects.select_related('turno').filter(trabajador=trabajador, fecha__in=fechas)}
    resultado = {'programadas':0, 'actualizadas':0, 'reabiertas':0, 'sin_cambios':0}
    for fecha in fechas:
        anterior = anteriores.get(fecha)
        r = por_fecha.get(fecha)
        if anterior and anterior.turno_id == turno.pk and (not r or r.turno_aplicado_id == turno.pk):
            resultado['sin_cambios'] += 1
            continue
        previo = str(anterior.turno) if anterior else (str(r.turno_aplicado) if r and r.turno_aplicado_id else 'Sin programación')
        ProgramacionHorario.objects.update_or_create(trabajador=trabajador, fecha=fecha, defaults={'turno':turno,'motivo':motivo,'responsable':actor})
        resultado['programadas'] += 1
        descripcion = f'Trabajador #{trabajador.pk} {trabajador.nombre_completo}; fecha {fecha}; anterior: {previo}; nuevo: {turno}; {motivo}'
        if r and r.turno_aplicado_id != turno.pk:
            resultado['reabiertas'] += int(r.verificado_contabilidad)
            r.turno_aplicado = turno
            r.save(update_fields=['turno_aplicado'])
            actualizar_tardanza(r)
            dejar_pendiente(r, actor, 'Cambio de horario confirmado. Requiere nueva revisión.')
            resultado['actualizadas'] += 1
        registrar_historial(r, actor, 'Horario programado', descripcion)
    if turno.hora_salida < turno.hora_entrada:
        from asistencia.services.jornadas_nocturnas import reagrupar_nocturnas
        resultado['reagrupadas'] = reagrupar_nocturnas(trabajador, fechas, actor)
    else:
        resultado['reagrupadas'] = 0
    return resultado
