"""Reglas operativas; no inventan marcas, descansos ni horas remuneradas."""
import unicodedata
from datetime import date, timedelta
from django.db.models import Q
from asistencia.models import ReglaJornada, DiaEspecial


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto or '') if not unicodedata.combining(c)).strip().casefold()


def programacion_descanso(resumen):
    from asistencia.models import DescansoProgramado
    if not resumen.trabajador_id:
        return None
    reglas = getattr(resumen, '_descansos_programados', None)
    if reglas is None:
        reglas = DescansoProgramado.objects.filter(trabajador_id=resumen.trabajador_id, desde__lte=resumen.fecha, hasta__gte=resumen.fecha)
    vigente = next((r for r in reglas if r.desde <= resumen.fecha <= r.hasta), None)
    return vigente if vigente is not None and resumen.fecha.weekday() in vigente.dias else None


def descanso_previsto(resumen):
    return programacion_descanso(resumen) is not None


def regla_para(persona, fecha, *, reglas=None):
    from asistencia.models import Trabajador
    if not isinstance(persona, Trabajador):
        persona = Trabajador.objects.filter(usuario=persona).first()
    area = normalizar(persona.area) if persona else ''
    if reglas is None:
        reglas = ReglaJornada.objects.filter(desde__lte=fecha).filter(Q(hasta__isnull=True) | Q(hasta__gte=fecha))
    candidatas = [r for r in reglas if r.desde <= fecha and (r.hasta is None or r.hasta >= fecha)
                  and ((r.trabajador_id == persona.pk if r.trabajador_id and persona else False)
                       or (not r.trabajador_id and (not r.area or normalizar(r.area) == area)))]
    return max(candidatas, key=lambda r: (bool(r.trabajador_id), bool(r.area), r.desde, r.pk), default=None)


def regla_resumen(resumen):
    if not hasattr(resumen, '_regla_jornada'):
        resumen._regla_jornada = regla_para(resumen.persona, resumen.fecha)
    return resumen._regla_jornada


def trabajo_efectivo(resumen, tramos):
    segundos = sum((t['fin'] - t['inicio']).total_seconds() for t in tramos)
    return max(0, segundos - getattr(resumen, 'conceptos_editados', {}).get('refrigerio_confirmado', 0))


def feriados_nacionales(anio):
    # Fuente: https://www.gob.pe/feriados y /feriados/historicos (verificado 30/10/2026).
    fijos = {(1, 1): 'Año Nuevo', (5, 1): 'Día del Trabajo', (6, 7): 'Batalla de Arica y Día de la Bandera',
             (6, 29): 'San Pedro y San Pablo', (7, 23): 'Día de la Fuerza Aérea del Perú',
             (7, 28): 'Fiestas Patrias', (7, 29): 'Fiestas Patrias', (8, 6): 'Batalla de Junín',
             (8, 30): 'Santa Rosa de Lima', (10, 8): 'Combate de Angamos', (11, 1): 'Todos los Santos',
             (12, 8): 'Inmaculada Concepción', (12, 9): 'Batalla de Ayacucho', (12, 25): 'Navidad'}
    # Cómputo gregoriano de Pascua para Jueves y Viernes Santo.
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    pascua = date(anio, mes, dia + 1)
    fechas = {date(anio, mes, dia): nombre for (mes, dia), nombre in fijos.items()}
    fechas[pascua - timedelta(days=3)] = 'Jueves Santo'
    fechas[pascua - timedelta(days=2)] = 'Viernes Santo'
    return fechas


def calendario_especial(desde, hasta):
    fechas = {}
    for anio in range(desde.year, hasta.year + 1):
        fechas.update(feriados_nacionales(anio))
    fechas.update(DiaEspecial.objects.filter(fecha__range=(desde, hasta)).values_list('fecha', 'nombre'))
    return fechas


def es_area_contable(resumen):
    area = normalizar(getattr(resumen.persona, 'area', ''))
    return any(nombre in area for nombre in ('contabilidad', 'contable', 'contadora', 'contador', 'tesoreria', 'tesorera', 'tesorero'))


def es_area_vigilancia(resumen):
    area = normalizar(getattr(resumen.persona, 'area', ''))
    return 'vigilante' in area or 'vigilancia' in area


def nocturnas_automaticas(resumen, *, respetar_cierre=True):
    if respetar_cierre and 'nocturnas_automaticas' in resumen.conceptos_editados:
        return resumen.conceptos_editados['nocturnas_automaticas']
    configurado = getattr(resumen.persona, 'calcular_nocturnas', None)
    return configurado if configurado is not None else not es_area_vigilancia(resumen)


def base_contable(resumen):
    """Base por marcas válidas: general 8:45/8:00; Contabilidad 9:30/8:30."""
    contabilidad = es_area_contable(resumen)
    if contabilidad and resumen.fecha.weekday() == 5:
        return 270 * 60
    marcas = getattr(resumen, '_marcas_base_contable', None)
    if marcas is None:
        from asistencia.models import MarcacionBiometrica
        from asistencia.services.revision import ventana_jornada, marcas_persona
        inicio, fin = ventana_jornada(resumen)
        consulta = MarcacionBiometrica.objects.filter(marcas_persona(resumen), fecha_hora__gte=inicio, fecha_hora__lte=fin, es_valida=True)
        if resumen.marcaciones_publicadas is not None:
            consulta = consulta.filter(pk__in=resumen.marcaciones_publicadas)
        marcas = list(consulta.select_related('correccion_evento').distinct().order_by('fecha_hora', 'pk'))
        cantidad = len(marcas)
    else:
        cantidad = sum(m.es_valida for m in marcas)
    if cantidad > 4 and not contabilidad:
        # Varios ciclos confirmados forman una sola base diaria, sin contar los intervalos fuera del trabajo.
        estado = 'fuera'
        ingresos = 0
        for marca in marcas:
            if not marca.es_valida:
                continue
            correccion = getattr(marca, 'correccion_evento', None)
            evento = correccion.tipo_evento if correccion else marca.tipo_evento
            if evento == 'ENTRADA' and estado == 'fuera':
                estado = 'trabajo'
                ingresos += 1
            elif evento == 'SALIDA' and estado == 'trabajo':
                estado = 'fuera'
            elif evento == 'SALIDA_REFRIGERIO' and estado == 'trabajo':
                estado = 'refrigerio'
            elif evento == 'RETORNO_REFRIGERIO' and estado == 'refrigerio':
                estado = 'trabajo'
            else:
                return None
        return 480 * 60 if estado == 'fuera' and ingresos > 1 else None
    if cantidad not in (2, 4):
        return None
    if not contabilidad:
        return (525 if cantidad == 2 else 480) * 60
    return (570 if cantidad == 2 else 510) * 60


def solo_horas_trabajadas(resumen):
    return resumen.conceptos_editados.get('solo_horas_trabajadas', getattr(resumen.persona, 'solo_horas_trabajadas', False))


def calcular_extra(resumen, porcentaje):
    if solo_horas_trabajadas(resumen):
        return False
    clave = f'calcular_extras_{porcentaje}'
    return resumen.conceptos_editados.get(clave, getattr(resumen.persona, clave, True))
