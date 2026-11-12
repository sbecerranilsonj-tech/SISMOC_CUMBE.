"""Recuperar una jornada omitida con horas confirmadas y procedencia manual."""
from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from asistencia.services.revision import comprobar_abierto, detalle_jornada, registrar_historial, marcas_persona
from asistencia.models import MarcacionBiometrica
from asistencia.services.marcacion_manual import agregar_marcacion_manual


@transaction.atomic
def registrar_trabajo_omitido(resumen, datos, actor):
    comprobar_abierto(resumen.fecha)
    if resumen.verificado_contabilidad:
        raise ValidationError('Reabra el día aprobado antes de registrar trabajo.')
    motivo = datos.get('motivo_olvido', '').strip()
    if not motivo or len(motivo) > 1000:
        raise ValidationError('Indique el motivo del olvido y cómo confirmó las horas (máximo 1000 caracteres).')
    detalle = detalle_jornada(resumen, incluir_formulario=False)
    if (any(m.es_valida for m in detalle['marcas']) or resumen.ajustes.exists()
            or MarcacionBiometrica.objects.filter(marcas_persona(resumen), fecha_hora__date=resumen.fecha, es_valida=True).exists()):
        raise ValidationError('El día ya tiene marcaciones o ajustes. Complete las marcas faltantes desde Ver detalle.')
    eventos = [('entrada_olvido', 'ENTRADA'), ('inicio_refrigerio_olvido', 'SALIDA_REFRIGERIO'),
               ('fin_refrigerio_olvido', 'RETORNO_REFRIGERIO'), ('salida_olvido', 'SALIDA')]
    if bool(datos.get(eventos[1][0])) != bool(datos.get(eventos[2][0])):
        raise ValidationError('Registre las dos horas del refrigerio o deje ambas vacías.')
    instantes = []
    for campo, evento in eventos:
        valor = datos.get(campo, '')
        if not valor and campo in {'inicio_refrigerio_olvido', 'fin_refrigerio_olvido'}:
            continue
        try:
            instante = datetime.fromisoformat(valor)
            if timezone.is_aware(instante):
                raise ValueError
            instante = timezone.make_aware(instante)
        except (ValueError, TypeError):
            raise ValidationError('Complete las fechas y horas confirmadas de entrada y salida.')
        comprobar_abierto(timezone.localtime(instante).date())
        if instante > timezone.now():
            raise ValidationError('No se pueden registrar horas futuras.')
        instantes.append((instante, evento))
    if (timezone.localtime(instantes[0][0]).date() != resumen.fecha
            or instantes[-1][0] - instantes[0][0] >= timedelta(days=1)
            or any(a[0] >= b[0] for a, b in zip(instantes, instantes[1:]))):
        raise ValidationError('Las horas deben estar en orden, iniciar en el día elegido y durar menos de 24 horas.')
    # Conservar el motivo anterior en auditoría antes de sustituir el no laborado.
    no_laborados = {'PERMISO', 'DESCANSO_SEMANAL', 'FERIADO_NO_LABORADO', 'NO_LABORO',
                   'VACACIONES', 'DESCANSO_MEDICO', 'CAMBIO_DESCANSO'}
    for incidencia in resumen.incidencias.filter(minutos__isnull=True):
        if incidencia.tipo not in no_laborados and not (
                incidencia.tipo == 'OTRO' and incidencia.motivo == 'Día no trabajado pendiente de justificar'):
            continue
        registrar_historial(resumen, actor, 'Situación sustituida por trabajo confirmado',
            f'{incidencia.get_tipo_display()}: {incidencia.motivo}. Aprobación anterior: {incidencia.aprobado_el or "pendiente"}. {motivo}')
        incidencia.delete()
    if hasattr(resumen, '_prefetched_objects_cache'):
        resumen._prefetched_objects_cache.clear()
    resumen.estado = 'POR_REVISAR'
    resumen.marcaciones_publicadas = []
    resumen.save(update_fields=['estado', 'marcaciones_publicadas'])
    for instante, evento in instantes:
        local = timezone.localtime(instante)
        agregar_marcacion_manual(resumen, {'fecha_manual': local.date().isoformat(),
            'hora_manual': local.time().isoformat(), 'tipo_evento_manual': evento,
            'motivo_manual': motivo}, actor)
    registrar_historial(resumen, actor, 'Trabajo sin marcaciones registrado',
        f'{len(instantes)} marcaciones manuales. {motivo}. Pendiente de revisión contable.')

