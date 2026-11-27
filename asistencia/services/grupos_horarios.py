"""Resumen visual por mes, trabajador y turno; conserva las fechas individuales."""
from asistencia.forms_horarios import DIAS


def agrupar_programacion(programaciones):
    grupos = {}
    for p in programaciones:
        clave = (p.fecha.year, p.fecha.month, p.trabajador_id, p.turno_id)
        if clave not in grupos:
            grupos[clave] = {'mes': p.fecha.replace(day=1), 'trabajador': p.trabajador,
                             'turno': p.turno, 'fechas': []}
        grupos[clave]['fechas'].append(p)
    resultado = list(grupos.values())
    for grupo in resultado:
        fechas = sorted(grupo['fechas'], key=lambda p: p.fecha)
        grupo.update(fechas=fechas, desde=fechas[0].fecha, hasta=fechas[-1].fecha,
                     total=len(fechas), dias=', '.join(dict(DIAS)[dia] for dia in sorted({p.fecha.weekday() for p in fechas})))
    return sorted(resultado, key=lambda g: (-g['mes'].toordinal(), g['trabajador'].nombre_completo, g['desde'], g['turno'].pk))
