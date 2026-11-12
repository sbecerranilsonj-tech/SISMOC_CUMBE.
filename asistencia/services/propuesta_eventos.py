"""Sugerir eventos para revisión, sin cambiar las marcaciones originales."""
from django.utils import timezone

SECUENCIA = ('ENTRADA', 'SALIDA_REFRIGERIO', 'RETORNO_REFRIGERIO', 'SALIDA')


def proponer_eventos(resumen, marcas):
    if resumen.verificado_contabilidad:
        return {}
    validas = sorted((m for m in marcas if m.es_valida), key=lambda m:(m.fecha_hora,m.pk))
    if not validas:
        return {}
    primera = validas[0]
    # Una salida aislada del día siguiente no acredita el ingreso del día anterior.
    if timezone.localtime(primera.fecha_hora).date() != resumen.fecha:
        return {}
    efectivos = {m.pk:getattr(getattr(m,'correccion_evento',None),'tipo_evento',m.tipo_evento) for m in validas}
    unicas = len({m.fecha_hora for m in validas}) == len(validas)
    from asistencia.services.reglas_jornada import es_area_contable, es_area_vigilancia
    if len(validas) == 2 and unicas and (es_area_contable(resumen) or es_area_vigilancia(resumen)) and (validas[-1].fecha_hora - primera.fecha_hora).total_seconds() < 86400:
        pareja = ('ENTRADA', 'SALIDA')
        if all(efectivos[m.pk] in ('SIN_CLASIFICAR', esperado) for m, esperado in zip(validas, pareja)):
            return {m.pk: evento for m, evento in zip(validas, pareja) if efectivos[m.pk] == 'SIN_CLASIFICAR'}
    completas = len(validas)==4 and unicas and (validas[-1].fecha_hora-primera.fecha_hora).total_seconds()<86400
    # Dos pares separados por un descanso mayor que el trabajo de ambos pares
    # pueden ser el final de una noche y el inicio de otra. Sin horario confirmado,
    # no convertir ese descanso en refrigerio ni la madrugada en una entrada.
    if completas and not (resumen.turno_aplicado or resumen.persona.turno):
        pausa = validas[2].fecha_hora - validas[1].fecha_hora
        trabajo = (validas[1].fecha_hora - validas[0].fecha_hora) + (validas[3].fecha_hora - validas[2].fecha_hora)
        if pausa > trabajo:
            return {}
    # Una clasificación ya registrada tiene prioridad sobre el orden propuesto.
    if completas and all(efectivos[m.pk] in ('SIN_CLASIFICAR', esperado) for m,esperado in zip(validas,SECUENCIA)):
        return {m.pk:evento for m,evento in zip(validas,SECUENCIA) if efectivos[m.pk]=='SIN_CLASIFICAR'}
    if efectivos[primera.pk]=='SIN_CLASIFICAR' and sum(m.fecha_hora==primera.fecha_hora for m in validas)==1:
        return {primera.pk:'ENTRADA'}
    return {}
