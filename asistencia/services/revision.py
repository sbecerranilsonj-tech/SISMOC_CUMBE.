"""Consulta y revisión de jornadas sin sobrescribir los resultados de origen."""
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from asistencia.models import (
    MarcacionBiometrica, ResumenAsistenciaDiaria, RevisionAsistencia,
    CierreAsistencia,
)
from asistencia.services.cuadro_excel import construir_cuadro_excel, base_jornada_segundos

CONCEPTOS_HORAS = ("horas_trabajadas", "horas_extras_25", "horas_extras_35", "horas_nocturnas")
GESTORES = {"ADMINISTRADOR", "CONTADORA", "GERENTE_GENERAL"}


def puede_gestionar(usuario):
    return usuario.is_active and usuario.esta_activo and (usuario.is_superuser or usuario.rol in GESTORES)


def puede_aprobar(usuario):
    return puede_gestionar(usuario) and (usuario.is_superuser or usuario.rol in {"CONTADORA", "GERENTE_GENERAL"})


def estado_revision(resumen):
    if resumen.verificado_contabilidad:
        return "APROBADO"
    return "OBSERVADO" if resumen.estado_revision == "OBSERVADO" else "PENDIENTE"


def comprobar_abierto(fecha):
    if CierreAsistencia.objects.filter(fecha_inicio__lte=fecha, fecha_fin__gte=fecha).exists():
        raise ValidationError("La jornada pertenece a un periodo cerrado. No se pueden modificar sus datos.")


def registrar_historial(resumen, actor, accion, detalle="", marcacion=None):
    return RevisionAsistencia.objects.create(
        resumen=resumen, responsable=actor, accion=accion, detalle=detalle, marcacion=marcacion,
    )


def dejar_pendiente(resumen, actor, motivo):
    resumen.estado_revision = "PENDIENTE"
    resumen.verificado_contabilidad = False
    resumen.revisado_por = None
    resumen.fecha_revision = None
    resumen.save(update_fields=["estado_revision", "verificado_contabilidad", "revisado_por", "fecha_revision"])
    registrar_historial(resumen, actor, "Revisión pendiente", motivo)


def valores_ajustados(resumen):
    valores = {key: Decimal(str(getattr(resumen, key))) for key in CONCEPTOS_HORAS}
    from asistencia.services.reglas_jornada import nocturnas_automaticas
    if not nocturnas_automaticas(resumen):
        valores['horas_nocturnas'] = Decimal(0)
    valores.update(descanso_feriado=Decimal(0), descuento=Decimal(0), compensacion=Decimal(0))
    for ajuste in resumen.ajustes.all():
        if ajuste.aprobado_el:
            exacto = resumen.conceptos_editados.get('feriado_segundos', {})
            valores[ajuste.concepto] += (Decimal(exacto[str(ajuste.pk)]) / Decimal(3600) if str(ajuste.pk) in exacto else Decimal(ajuste.minutos) / Decimal(60))
    for concepto, segundos in resumen.conceptos_editados.items():
        if concepto in {'horas_extras_25', 'horas_extras_35', 'horas_nocturnas'}:
            valores[concepto] = Decimal(segundos) / Decimal(3600)
    from asistencia.services.reglas_jornada import solo_horas_trabajadas
    if solo_horas_trabajadas(resumen):
        valores['horas_extras_25'] = valores['horas_extras_35'] = Decimal(0)
    from asistencia.services.reglas_jornada import calcular_extra
    for porcentaje in (25, 35):
        if not calcular_extra(resumen, porcentaje):
            valores[f'horas_extras_{porcentaje}'] = Decimal(0)
    return valores


def ventana_jornada(resumen):
    """Usa los límites guardados; nunca une arbitrariamente todas las marcas de dos días."""
    turno = resumen.turno_aplicado or resumen.persona.turno
    if resumen.conceptos_editados.get('inicio_archivo_sin_entrada'):
        from asistencia.services.jornadas_nocturnas import corte_descanso
        dia = resumen.fecha + timedelta(days=1)
        return (timezone.make_aware(datetime.combine(dia, datetime.min.time())),
                timezone.make_aware(datetime.combine(dia, corte_descanso(turno))))
    inicio = datetime.combine(resumen.fecha, resumen.primera_entrada or datetime.min.time())
    if resumen.ultima_salida and resumen.primera_entrada:
        fin = datetime.combine(resumen.fecha, resumen.ultima_salida)
        if fin < inicio:
            fin += timedelta(days=1)
    else:
        fin = datetime.combine(resumen.fecha + timedelta(days=1), datetime.min.time())
        if turno and turno.hora_salida < turno.hora_entrada:
            fin = datetime.combine(resumen.fecha + timedelta(days=1), turno.hora_salida)
    return timezone.make_aware(inicio), timezone.make_aware(fin)


def marcas_persona(resumen):
    if resumen.trabajador_id:
        consulta = Q(identidad_biometrica__trabajador_id=resumen.trabajador_id) | Q(filas_origen__identidad__trabajador_id=resumen.trabajador_id)
        if resumen.usuario_id:
            consulta |= Q(usuario_id=resumen.usuario_id)
        return consulta
    return Q(usuario_id=resumen.usuario_id) | Q(usuario__isnull=True, dni=resumen.persona.dni)


def detalle_jornada(resumen, *, marcas_consulta=None, incluir_formulario=True, cierre_confirmado=None):
    from asistencia.forms import MarcacionManualForm
    from asistencia.services.reglas_jornada import descanso_previsto, programacion_descanso
    turno = resumen.turno_aplicado or resumen.persona.turno
    inicio, fin = ventana_jornada(resumen)
    marcas = list(marcas_consulta) if marcas_consulta is not None else list(MarcacionBiometrica.objects.filter(
        marcas_persona(resumen),
        fecha_hora__gte=inicio, fecha_hora__lte=fin,
    ).select_related("carga_origen", "correccion_evento", "identidad_biometrica", "registrada_por").order_by("fecha_hora", "pk").distinct())
    if resumen.marcaciones_publicadas is not None:
        marcas = [m for m in marcas if m.pk in resumen.marcaciones_publicadas]
    resumen._marcas_base_contable = marcas
    alertas, tramos = [], []
    entrada = refrigerio = None
    trabajo_seg = refrigerio_seg = 0
    completa = True
    validas = [m for m in marcas if m.es_valida]
    for marca in marcas:
        correccion = getattr(marca, "correccion_evento", None)
        marca.evento_efectivo = correccion.tipo_evento if correccion else marca.tipo_evento
        marca.evento_etiqueta = dict(MarcacionBiometrica.TipoEvento.choices).get(marca.evento_efectivo, marca.evento_efectivo)
        marca.fecha_local = timezone.localtime(marca.fecha_hora)
        if not marca.es_valida:
            continue
        tipo = marca.evento_efectivo
        if tipo == "ENTRADA":
            if entrada or refrigerio:
                completa = False
            entrada = marca.fecha_hora
        elif tipo == "SALIDA_REFRIGERIO":
            if entrada is None or refrigerio:
                completa = False
            else:
                segundos = (marca.fecha_hora - entrada).total_seconds()
                trabajo_seg += segundos
                tramos.append({"inicio": timezone.localtime(entrada), "fin": marca.fecha_local, "duracion": duracion(segundos)})
                entrada = None
            refrigerio = marca.fecha_hora
        elif tipo == "RETORNO_REFRIGERIO":
            if refrigerio is None or entrada:
                completa = False
            else:
                refrigerio_seg += (marca.fecha_hora - refrigerio).total_seconds()
            refrigerio = None
            entrada = marca.fecha_hora
        elif tipo == "SALIDA":
            if entrada is None or refrigerio:
                completa = False
            else:
                segundos = (marca.fecha_hora - entrada).total_seconds()
                trabajo_seg += segundos
                tramos.append({"inicio": timezone.localtime(entrada), "fin": marca.fecha_local, "duracion": duracion(segundos)})
            entrada = None
        else:
            completa = False
    completa = bool(validas) and completa and entrada is None and refrigerio is None
    if completa and base_jornada_segundos(resumen) is None:
        completa = False
        alertas.append('Revise la clasificación y las duplicadas: no se puede determinar la jornada base con estas marcas.')
    if resumen.conceptos_editados.get('inicio_archivo_sin_entrada'):
        completa = False
        alertas.append('Marcación inicial sin pareja · Inicio del archivo. Falta la entrada de la noche anterior; no se calculan horas.')
    from asistencia.services.reglas_jornada import regla_resumen, trabajo_efectivo
    regla = regla_resumen(resumen)
    exenta = bool(regla and regla.exento_marcacion and not validas and resumen.horas_trabajadas == 0)
    refrigerio_marcado = any(m.evento_efectivo in {'SALIDA_REFRIGERIO', 'RETORNO_REFRIGERIO'} for m in validas)
    descuento_refrigerio = resumen.conceptos_editados.get('refrigerio_confirmado', 0)
    refrigerio_invalido = bool(descuento_refrigerio and (refrigerio_marcado or descuento_refrigerio > trabajo_seg))
    falta_refrigerio = bool(regla and regla.minutos_refrigerio and completa and not refrigerio_marcado
                            and base_jornada_segundos(resumen) >= 6 * 3600 and not descuento_refrigerio)
    from asistencia.services.reglas_jornada import es_area_contable, es_area_vigilancia, nocturnas_automaticas
    from asistencia.services.reglas_jornada import solo_horas_trabajadas
    if solo_horas_trabajadas(resumen) or len(validas) == 2:
        falta_refrigerio = False
    trabajo_seg = trabajo_efectivo(resumen, tramos)
    if descuento_refrigerio and not refrigerio_invalido:
        refrigerio_seg += descuento_refrigerio
    if not validas:
        alertas.append("No hay marcaciones válidas en el intervalo de la jornada.")
    elif not completa:
        alertas.append("Marcaciones incompletas o tipos de evento inconsistentes. Revise entrada, refrigerio y salida.")
    if resumen.primera_entrada and resumen.ultima_salida and resumen.ultima_salida < resumen.primera_entrada:
        alertas.append("La salida se consulta al día siguiente porque su hora es anterior a la entrada. Confirme el cruce de medianoche.")
    if completa and abs(Decimal(str(trabajo_seg / 3600)) - Decimal(str(resumen.horas_trabajadas))) > Decimal("0.02"):
        alertas.append("Las horas guardadas difieren del tiempo reconstruido por marcaciones. Registre un ajuste si corresponde.")
    valores = valores_ajustados(resumen)
    if any(valores[key] < 0 for key in CONCEPTOS_HORAS + ("descanso_feriado", "descuento", "compensacion") if key != "horas_extras_25"):
        alertas.append("Hay un concepto con total negativo. Revise los ajustes.")
    pendientes = any(not i.aprobado_el for i in resumen.incidencias.all()) or any(not a.aprobado_el for a in resumen.ajustes.all())
    if pendientes:
        alertas.append("Existen incidencias o ajustes pendientes de aprobación.")
    justificada = resumen.horas_trabajadas == 0 and resumen.estado in {"VACACIONES", "PERMISO", "DESCANSO_MEDICO", "DIA_LIBRE", "DESCANSO_SUTRAN", "FALTA", "FERIADO", "NO_LABORO"}
    if justificada and resumen.estado != "FALTA":
        justificada = any(i.aprobado_el and i.minutos is None for i in resumen.incidencias.all())
    justificada = justificada or exenta
    tipos_no_laborados = {"SIN_PROGRAMACION", "DESCANSO_SEMANAL", "FERIADO_NO_LABORADO", "VACACIONES", "PERMISO", "DESCANSO_MEDICO", "CAMBIO_DESCANSO", "NO_LABORO", "CUMPLEANOS"}
    situaciones = [i for i in resumen.incidencias.all() if i.minutos is None and (i.tipo in tipos_no_laborados or (i.tipo == "OTRO" and i.motivo == "Día no trabajado pendiente de justificar"))]
    situacion_dia = max(situaciones, key=lambda i: i.pk) if situaciones and not validas and resumen.horas_trabajadas == 0 else None
    solo_situacion = bool(situacion_dia) and not resumen.ajustes.exists()
    if justificada or situacion_dia:
        alertas = [a for a in alertas if a not in {"No hay marcaciones válidas en el intervalo de la jornada.", "Trabajador sin turno asignado."}]
    diferencia = completa and abs(Decimal(str(trabajo_seg / 3600)) - valores["horas_trabajadas"]) > Decimal("0.02")
    deficit = None
    if completa:
        base = base_jornada_segundos(resumen)
        if base is not None:
            deficit = max(0, round((base - trabajo_seg) / 60))
    bloqueos = []
    descanso = programacion_descanso(resumen)
    decision_descanso = resumen.conceptos_editados.get('situacion_descanso', {})
    descanso_confirmado = bool(descanso and decision_descanso.get('programacion_id') == descanso.pk
                              and decision_descanso.get('tipo') in {'DESCANSO_TRABAJADO', 'CAMBIO_DESCANSO'})
    trabajo_en_descanso = descanso is not None and bool(validas)
    if trabajo_en_descanso and not descanso_confirmado:
        bloqueos.append('Confirme si fue descanso trabajado o cambio de descanso antes de aprobar.')
    if falta_refrigerio:
        alertas.append('Refrigerio sin marcar. Confirme el descanso antes de calcular las horas efectivas.')
        bloqueos.append('Confirme el refrigerio sin marcar o registre las marcaciones que faltan.')
    if refrigerio_invalido:
        bloqueos.append('Retire el descuento de refrigerio confirmado: ya existen marcas de refrigerio o supera el tiempo trabajado.')
    if not completa and not justificada and not situacion_dia:
        bloqueos.append("Complete o corrija las marcaciones; una ausencia justificada requiere una incidencia de día completo aprobada.")
    if diferencia:
        bloqueos.append("Concilie las horas efectivas con los tramos mediante un ajuste.")
    if pendientes:
        bloqueos.append("Apruebe la situación del día registrada." if solo_situacion else "Apruebe las incidencias y los ajustes pendientes.")
    if situacion_dia and not justificada and not pendientes:
        bloqueos.append("Complete la justificación del día no trabajado antes de aprobarlo.")
    if any(v < 0 for k, v in valores.items() if k != "horas_extras_25"):
        bloqueos.append("Los conceptos no pueden quedar con total negativo.")
    from asistencia.services.propuesta_eventos import proponer_eventos
    cerrada = cierre_confirmado if cierre_confirmado is not None else CierreAsistencia.objects.filter(fecha_inicio__lte=resumen.fecha, fecha_fin__gte=resumen.fecha).exists()
    propuestas = {} if cerrada else proponer_eventos(resumen, marcas)
    for marca in marcas:
        marca.evento_seleccionado = propuestas.get(marca.pk, marca.evento_efectivo)
    cuadro = construir_cuadro_excel(resumen, marcas, tramos, completa and not falta_refrigerio and not refrigerio_invalido, turno, valores, refrigerio_seg)
    from asistencia.services.duplicadas import pares_cercanos, ultimas_revisiones, EXCLUIR
    cercanas = pares_cercanos(marcas)
    exclusiones = getattr(resumen, '_exclusiones_revision', None)
    if exclusiones is None:
        exclusiones = ultimas_revisiones([m for m in marcas if not m.es_valida]) if any(not m.es_valida for m in marcas) else {}
    for fila in cuadro['filas']:
        fila['evento_seleccionado'] = propuestas.get(fila['marcacion_id'], fila['evento_codigo'])
        fila['es_propuesta'] = fila['marcacion_id'] in propuestas
        fila['posible_duplicada'] = fila['marcacion_id'] in cercanas
        fila['excluida_duplicada'] = not fila['valida'] and exclusiones.get(fila['marcacion_id']) == EXCLUIR
    estado_visible = resumen.get_estado_display() if turno or justificada or situacion_dia else ("Control por jornada · Sin horario fijo asignado" if es_area_contable(resumen) else "Horario por confirmar")
    if turno and not turno.evaluar_tardanzas and resumen.estado == 'TARDANZA':
        estado_visible = 'Control por horario · Sin evaluación de tardanza'
    if resumen.conceptos_editados.get('inicio_archivo_sin_entrada'):
        estado_visible = 'Marcación inicial sin pareja · Inicio del archivo'
    return {
        "resumen": resumen, "turno": turno, "marcas": marcas, "tramos": tramos,
        "descanso_previsto": descanso_previsto(resumen),
        "sin_trabajo_programado": bool(descanso and descanso.sin_trabajo_programado),
        "trabajo_en_descanso": trabajo_en_descanso,
        "descanso_confirmado": descanso_confirmado,
        "decision_descanso": decision_descanso if descanso_confirmado else {},
        "nocturnas_automaticas": nocturnas_automaticas(resumen),
        "nocturnas_configuradas": nocturnas_automaticas(resumen, respetar_cierre=False),
        "propuestas_eventos": propuestas,
        "tardanza_confirmada": turno is not None and turno.evaluar_tardanzas and completa,
        "control_por_jornada": es_area_contable(resumen) and turno is None,
        "estado_asistencia_visible": estado_visible,
        "form_marca_manual": MarcacionManualForm(resumen=resumen) if incluir_formulario else None,
        "alertas": alertas, "bloqueos": bloqueos, "completa": completa,
        "ausencia_justificada": justificada,
        "exenta_marcacion": exenta, "regla_jornada": regla,
        "falta_refrigerio": falta_refrigerio,
        "refrigerio_confirmado": bool(descuento_refrigerio),
        "situacion_dia": situacion_dia, "solo_situacion": solo_situacion,
        "refrigerio": duracion(refrigerio_seg) if completa and not falta_refrigerio and not refrigerio_invalido else None,
        "trabajo_reconstruido": duracion(trabajo_seg) if completa and not falta_refrigerio and not refrigerio_invalido else None,
        "deficit_minutos": deficit,
        "cuadro_excel": cuadro,
        "filas_duplicadas": [f for f in cuadro['filas'] if f['posible_duplicada'] or f['excluida_duplicada']],
        "valores": valores, "revision": estado_revision(resumen),
        "cerrada": cerrada,
        "inicio_consulta": timezone.localtime(inicio), "fin_consulta": timezone.localtime(fin),
        "cruza_medianoche": fin.date() > inicio.date() and bool(marcas) and any(timezone.localtime(m.fecha_hora).date() > resumen.fecha for m in marcas),
    }


def duracion(segundos):
    segundos = int(round(segundos))
    return f"{segundos // 3600:02d}:{segundos % 3600 // 60:02d}:{segundos % 60:02d}"


def revisar(resumen, actor, decision, motivo="", *, situacion_confirmada=None):
    comprobar_abierto(resumen.fecha)
    if decision == "APROBADO":
        if not puede_aprobar(actor):
            raise ValidationError("La aprobación corresponde a Contabilidad o Gerencia.")
        detalle = detalle_jornada(resumen, incluir_formulario=False)
        if detalle['solo_situacion'] and situacion_confirmada != detalle['situacion_dia'].tipo:
            raise ValidationError('Seleccione la situación del día antes de aprobarlo desde su fila.')
        bloqueos = detalle["bloqueos"]
        if bloqueos:
            raise ValidationError(bloqueos)
    elif decision == "OBSERVADO":
        if not puede_gestionar(actor):
            raise ValidationError("No tiene permiso para observar jornadas.")
        if not motivo.strip():
            raise ValidationError("Indique el motivo de la observación.")
    else:
        raise ValidationError("Estado de revisión no válido.")
    resumen.estado_revision = decision
    resumen.verificado_contabilidad = decision == "APROBADO"
    resumen.revisado_por = actor
    resumen.fecha_revision = timezone.now()
    resumen.save(update_fields=["estado_revision", "verificado_contabilidad", "revisado_por", "fecha_revision"])
    registrar_historial(resumen, actor, "Jornada aprobada" if decision == "APROBADO" else "Jornada observada", motivo)
