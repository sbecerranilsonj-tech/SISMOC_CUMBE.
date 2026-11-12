"""Prioridades contables a partir de las jornadas visibles y sus detalles vigentes."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from asistencia.services.revision_trabajador import dia_validado, lista_para_aprobar


def resumen_dashboard(detalles, filtros, cierres):
    filas = {}
    counts = defaultdict(int)
    horas = {estado: {'he25': Decimal(0), 'he35': Decimal(0)} for estado in ('aprobadas', 'pendientes')}
    for d in detalles:
        r = d['resumen']
        persona = r.persona
        fila = filas.setdefault(persona.dni, {'persona': persona, 'por_validar': 0, 'listas': 0, 'observadas': 0, 'situaciones': 0})
        aprobado = r.verificado_contabilidad
        counts['aprobadas'] += int(aprobado)
        if not aprobado:
            por_validar = not dia_validado(d) or (bool(d['bloqueos']) and not d['solo_situacion'])
            lista = lista_para_aprobar(d)
            observada = r.estado_revision == 'OBSERVADO'
            situacion = bool(d['solo_situacion'])
            for clave, valor in [('por_validar', por_validar), ('listas', lista), ('observadas', observada), ('situaciones', situacion)]:
                counts[clave] += int(valor)
                fila[clave] += int(valor)
        bucket = horas['aprobadas' if aprobado else 'pendientes']
        bucket['he25'] += d['valores']['horas_extras_25']
        bucket['he35'] += d['valores']['horas_extras_35']
    query = {k: filtros[k] for k in ('desde', 'hasta', 'sede', 'trabajador', 'estado', 'revision') if filtros.get(k)}
    prioridades = []
    for fila in filas.values():
        if not any(fila[k] for k in ('por_validar', 'listas', 'observadas', 'situaciones')):
            continue
        fila['url'] = '?' + urlencode({**query, 'vista': 'asistencia', 'persona_dni': fila['persona'].dni})
        fila['accion'] = 'Revisar' if fila['por_validar'] or fila['observadas'] or fila['situaciones'] else 'Ver para aprobar'
        prioridades.append(fila)
    prioridades.sort(key=lambda f: (-f['observadas'], -f['por_validar'], -f['situaciones'], -f['listas'], f['persona'].nombre_completo.casefold()))
    inicio, fin = date.fromisoformat(filtros['desde']), date.fromisoformat(filtros['hasta'])
    siguiente = inicio
    coincidentes = sorted((c for c in cierres if c.fecha_inicio <= fin and c.fecha_fin >= inicio), key=lambda c: c.fecha_inicio)
    for c in coincidentes:
        if c.fecha_inicio > siguiente:
            break
        siguiente = max(siguiente, c.fecha_fin + timedelta(days=1))
    cierre = 'Cerrado' if siguiente > fin else ('Cierre parcial' if coincidentes else 'Abierto')
    return {
        **{k: counts[k] for k in ('aprobadas', 'por_validar', 'listas', 'observadas', 'situaciones')},
        'trabajadores': len(filas), 'jornadas': len(detalles), 'horas': horas,
        'prioridades': prioridades, 'total_prioridades': len(prioridades), 'cierre': cierre,
        'url_asistencia': '?' + urlencode({**query, 'vista': 'asistencia'}),
        'url_contabilidad': '?' + urlencode({**query, 'vista': 'contabilidad'}),
        'url_aprobadas': '?' + urlencode({**query, 'vista': 'contabilidad', 'revision': 'APROBADO'}),
    }
