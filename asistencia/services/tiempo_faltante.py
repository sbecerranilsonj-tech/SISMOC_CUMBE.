"""Acumular déficits diarios sin compensarlos con extras de otras fechas."""
from asistencia.services.cuadro_excel import base_jornada_segundos, formato_tiempo


def agregar_tiempo_faltante(filas, detalles):
    por_dni = {fila['usuario'].dni: fila for fila in filas}
    for fila in filas:
        fila['faltante_segundos'] = 0
        fila['faltante_por_revisar'] = 0
    for d in detalles:
        fila = por_dni.get(d['resumen'].persona.dni)
        if fila is None or d['solo_situacion'] or d['ausencia_justificada']:
            continue
        if not d['completa'] or d.get('falta_refrigerio'):
            fila['faltante_por_revisar'] += 1
            continue
        from asistencia.services.reglas_jornada import trabajo_efectivo
        trabajo = trabajo_efectivo(d['resumen'], d['tramos'])
        base = base_jornada_segundos(d['resumen'])
        if base is None:
            fila['faltante_por_revisar'] += 1
            continue
        fila['faltante_segundos'] += max(0, base - trabajo)
    for fila in filas:
        fila['tiempo_faltante'] = formato_tiempo(fila['faltante_segundos'])
    return formato_tiempo(sum(f['faltante_segundos'] for f in filas))
