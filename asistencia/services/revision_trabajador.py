"""Consulta y clasificación de las marcas de un trabajador en un periodo."""
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from asistencia.models import MarcacionBiometrica, CorreccionEvento, CierreAsistencia
from asistencia.services.revision import marcas_persona, ventana_jornada, detalle_jornada, comprobar_abierto, dejar_pendiente, registrar_historial
from asistencia.services.cuadro_excel import segundos_nocturnos, base_jornada_segundos


def filtrar_persona(queryset, dni):
    return queryset.filter(Q(trabajador__dni=dni) | Q(trabajador__isnull=True, usuario__dni=dni))


def marcas_del_periodo(jornadas):
    consulta = Q(pk__in=[])
    for resumen in jornadas:
        inicio, fin = ventana_jornada(resumen)
        propias = marcas_persona(resumen) & Q(fecha_hora__gte=inicio, fecha_hora__lte=fin)
        if resumen.marcaciones_publicadas is not None:
            propias &= Q(pk__in=resumen.marcaciones_publicadas)
        consulta |= propias
    return MarcacionBiometrica.objects.filter(consulta).distinct().select_related("identidad_biometrica", "correccion_evento", "carga_origen").order_by("fecha_hora", "pk")


def detalles_en_lote(jornadas):
    """Reconstruir el avance actual sin una consulta de marcas por cada día."""
    if not jornadas:
        return []
    from asistencia.models import ReglaJornada, DescansoProgramado
    descansos = list(DescansoProgramado.objects.filter(trabajador_id__in={r.trabajador_id for r in jornadas}, desde__lte=max(r.fecha for r in jornadas), hasta__gte=min(r.fecha for r in jornadas)))
    from asistencia.services.reglas_jornada import regla_para, calendario_especial
    especiales = calendario_especial(min(r.fecha for r in jornadas), max(r.fecha for r in jornadas))
    reglas = list(ReglaJornada.objects.filter(desde__lte=max(r.fecha for r in jornadas)))
    for resumen in jornadas:
        resumen._regla_jornada = regla_para(resumen.persona, resumen.fecha, reglas=reglas)
        resumen._calendario_feriados = especiales
        resumen._descansos_programados = [d for d in descansos if d.trabajador_id == resumen.trabajador_id]
    ventanas = {r.pk: ventana_jornada(r) for r in jornadas}
    trabajadores = {r.trabajador_id for r in jornadas if r.trabajador_id}
    usuarios = {r.usuario_id for r in jornadas if r.usuario_id}
    dnis = {r.persona.dni for r in jornadas if not r.trabajador_id}
    consulta = Q(identidad_biometrica__trabajador_id__in=trabajadores) | Q(filas_origen__identidad__trabajador_id__in=trabajadores) | Q(usuario_id__in=usuarios) | Q(usuario__isnull=True, dni__in=dnis)
    marcas = MarcacionBiometrica.objects.filter(consulta, fecha_hora__gte=min(v[0] for v in ventanas.values()), fecha_hora__lte=max(v[1] for v in ventanas.values())).distinct().select_related("identidad_biometrica", "correccion_evento", "carga_origen").prefetch_related("filas_origen__identidad").order_by("fecha_hora", "pk")
    por_trabajador, por_usuario, por_dni = defaultdict(dict), defaultdict(dict), defaultdict(dict)
    for marca in marcas:
        ids = {f.identidad.trabajador_id for f in marca.filas_origen.all() if f.identidad.trabajador_id}
        if marca.identidad_biometrica_id and marca.identidad_biometrica.trabajador_id:
            ids.add(marca.identidad_biometrica.trabajador_id)
        for tid in ids:
            por_trabajador[tid][marca.pk] = marca
        if marca.usuario_id:
            por_usuario[marca.usuario_id][marca.pk] = marca
        else:
            por_dni[marca.dni][marca.pk] = marca
    cierres = list(CierreAsistencia.objects.filter(fecha_inicio__lte=max(r.fecha for r in jornadas), fecha_fin__gte=min(r.fecha for r in jornadas)))
    detalles = []
    from asistencia.services.duplicadas import ultimas_revisiones
    exclusiones = ultimas_revisiones([m for conjunto in por_trabajador.values() for m in conjunto.values() if not m.es_valida] + [m for conjunto in por_usuario.values() for m in conjunto.values() if not m.es_valida] + [m for conjunto in por_dni.values() for m in conjunto.values() if not m.es_valida])
    for resumen in jornadas:
        resumen._exclusiones_revision = exclusiones
        candidatas = dict(por_trabajador[resumen.trabajador_id]) if resumen.trabajador_id else dict(por_dni[resumen.persona.dni])
        if resumen.usuario_id:
            candidatas.update(por_usuario[resumen.usuario_id])
        inicio, fin = ventanas[resumen.pk]
        propias = sorted((m for m in candidatas.values() if inicio <= m.fecha_hora <= fin), key=lambda m: (m.fecha_hora, m.pk))
        cerrado = any(c.fecha_inicio <= resumen.fecha <= c.fecha_fin for c in cierres)
        detalles.append(detalle_jornada(resumen, marcas_consulta=propias, incluir_formulario=False, cierre_confirmado=cerrado))
    return detalles


def dia_validado(detalle):
    return (detalle["completa"] and not detalle['falta_refrigerio']) or detalle["ausencia_justificada"]


def lista_para_aprobar(detalle):
    return not detalle["solo_situacion"] and not detalle["bloqueos"] and not detalle["cerrada"] and not detalle["resumen"].verificado_contabilidad and detalle["resumen"].estado_revision != "OBSERVADO"


def contexto_revision(jornadas, desde=None, hasta=None, *, detalles=None):
    cierres = list(CierreAsistencia.objects.all())
    # La reconstrucción en lote ya contiene las marcas autorizadas de cada jornada.
    # Reutilizarlas evita repetir una consulta con un OR por cada día del periodo.
    if detalles is None:
        marcas = list(marcas_del_periodo(jornadas))
    else:
        por_pk = {m.pk: m for d in detalles for m in d['marcas']}
        marcas = sorted(por_pk.values(), key=lambda m: (m.fecha_hora, m.pk))
    for marca in marcas:
        marca.fecha_local = timezone.localtime(marca.fecha_hora)
        correccion = getattr(marca, "correccion_evento", None)
        marca.evento_efectivo = correccion.tipo_evento if correccion else marca.tipo_evento
        marca.evento_etiqueta = dict(MarcacionBiometrica.TipoEvento.choices)[marca.evento_efectivo]
        marca.esta_cerrada = any(c.fecha_inicio <= marca.fecha_local.date() <= c.fecha_fin for c in cierres)
    detalles = detalles_en_lote(jornadas) if detalles is None else detalles
    propuestas = {pk:evento for d in detalles for pk,evento in d['propuestas_eventos'].items()}
    for marca in marcas:
        marca.evento_seleccionado = propuestas.get(marca.pk, marca.evento_efectivo)
        marca.es_propuesta = marca.pk in propuestas
    por_fecha = {d["resumen"].fecha: d for d in detalles}
    fecha = desde or min(por_fecha)
    fin = hasta or max(por_fecha)
    calendario = []
    from asistencia.services.reglas_jornada import calendario_especial, regla_para
    especiales = calendario_especial(fecha, fin)
    from asistencia.models import ReglaJornada
    reglas = list(ReglaJornada.objects.filter(desde__lte=fin))
    persona = jornadas[0].persona
    while fecha <= fin:
        regla = regla_para(persona, fecha, reglas=reglas)
        calendario.append({"fecha": fecha, "detalle": por_fecha.get(fecha), "cerrado": any(c.fecha_inicio <= fecha <= c.fecha_fin for c in cierres),
                           "es_sabado": fecha.weekday() == 5, "especial": especiales.get(fecha, ''),
                           "exenta": bool(regla and regla.exento_marcacion)})
        fecha += timedelta(days=1)
    persona = jornadas[0].persona
    abiertas = [d for d in detalles if not d['cerrada'] and not d['resumen'].verificado_contabilidad]
    horarios = {d['turno'].pk if d['turno'] else None for d in (abiertas or detalles)}
    horario_comun_id = next(iter(horarios)) if len(horarios) == 1 else None
    return {"persona": persona, "dni": persona.dni, "marcas": marcas, "detalles": detalles, "calendario": calendario,
            "horario_comun_id": horario_comun_id, "horarios_distintos": len(horarios) > 1,
            "validadas": sum(dia_validado(d) for d in detalles), "aprobadas": sum(d["resumen"].verificado_contabilidad for d in detalles),
            "listas_para_aprobar": sum(lista_para_aprobar(d) for d in detalles), "sin_registrar": len(calendario) - len(por_fecha),
            "area": getattr(persona, "area", "Por completar"),
            "codigo": persona.codigo if hasattr(persona, "codigo") else (persona.zkteco_user_id or "Sin código vinculado")}


def validar_periodo(jornadas, cambios, originales, turno, motivo, actor):
    """El llamador mantiene una transacción y bloquea las jornadas."""
    motivo = motivo or "Validación de marcaciones laborales."
    permitidas = {m.pk: m for m in marcas_del_periodo(jornadas)}
    if not set(cambios).issubset(permitidas):
        raise ValidationError("Una de las marcaciones no pertenece al trabajador o periodo seleccionado.")
    modificadas = 0
    # Bloquear las filas sin joins opcionales para no bloquear otras relaciones.
    bloqueadas = MarcacionBiometrica.objects.select_for_update().filter(pk__in=cambios).order_by("pk")
    for marca in bloqueadas:
        evento = cambios[marca.pk]
        if evento not in MarcacionBiometrica.TipoEvento.values and evento != 'EXCLUIR_DUPLICADA':
            raise ValidationError("Seleccione un tipo de marcación válido.")
        correccion = getattr(marca, "correccion_evento", None)
        actual = correccion.tipo_evento if correccion else marca.tipo_evento
        if originales.get(marca.pk) != actual:
            raise ValidationError("Otra revisión cambió las marcaciones. Cierre y abra de nuevo la ventana para actualizar los datos.")
        if evento == 'EXCLUIR_DUPLICADA':
            from asistencia.services.duplicadas import EXCLUIR
            if not marca.es_valida:
                raise ValidationError('La marca ya fue excluida. Actualice la ventana.')
            comprobar_abierto(timezone.localtime(marca.fecha_hora).date())
            marca.es_valida = False
            marca.save(update_fields=['es_valida'])
            registrar_historial(None, actor, EXCLUIR, 'Exclusión confirmada al clasificar: duplicada, no computar. ' + motivo, marca)
            modificadas += 1
            continue
        if evento == actual:
            continue
        if not marca.es_valida:
            raise ValidationError("Una marcación invalidada no puede clasificarse desde esta ventana.")
        comprobar_abierto(timezone.localtime(marca.fecha_hora).date())
        CorreccionEvento.objects.update_or_create(marcacion=marca, defaults={"tipo_evento": evento, "motivo": motivo, "responsable": actor})
        registrar_historial(None, actor, "Marcación clasificada por trabajador", f"Original: {marca.tipo_evento}; efectivo: {evento}. {motivo}", marca)
        modificadas += 1
    completas = pendientes = cerradas = 0
    for resumen in jornadas:
        if CierreAsistencia.objects.filter(fecha_inicio__lte=resumen.fecha, fecha_fin__gte=resumen.fecha).exists():
            cerradas += 1
            continue
        if resumen.verificado_contabilidad and not modificadas:
            completas += 1
            continue
        if turno and resumen.turno_aplicado_id != turno.pk:
            if resumen.trabajador_id:
                from asistencia.services.horarios import programar_horarios
                programar_horarios(resumen.trabajador, resumen.fecha, resumen.fecha, [resumen.fecha.weekday()], turno, motivo, actor)
                resumen.refresh_from_db()
            resumen.turno_aplicado = turno
            resumen.save(update_fields=["turno_aplicado"])
        detalle = detalle_jornada(resumen)
        if detalle["completa"] and not detalle['falta_refrigerio'] and not resumen.ajustes.exists():
            from asistencia.services.reglas_jornada import trabajo_efectivo
            trabajo = trabajo_efectivo(resumen, detalle['tramos'])
            valores = {"horas_trabajadas": trabajo, "horas_nocturnas": segundos_nocturnos(detalle["tramos"])}
            base = base_jornada_segundos(resumen)
            if base is not None:
                from asistencia.services.reglas_jornada import solo_horas_trabajadas
                extras = 0 if solo_horas_trabajadas(resumen) else trabajo - base
                valores.update(horas_extras_25=min(extras, 7200), horas_extras_35=max(0, extras - 7200))
            from asistencia.services.reglas_jornada import calcular_extra
            for porcentaje in (25, 35):
                if not calcular_extra(resumen, porcentaje):
                    valores[f'horas_extras_{porcentaje}'] = 0
            for campo, segundos in valores.items():
                setattr(resumen, campo, (Decimal(str(segundos)) / Decimal(3600)).quantize(Decimal("0.01")))
            campos = list(valores)
            resumen.save(update_fields=campos)
        from asistencia.services.horarios import actualizar_tardanza
        actualizar_tardanza(resumen, detalle)
        # Clasificar no equivale a aprobar: verificar de nuevo los bloqueos.
        detalle_final = detalle_jornada(resumen)
        if detalle_final["bloqueos"]:
            pendientes += 1
        else:
            completas += 1
        if modificadas or turno or not resumen.verificado_contabilidad:
            dejar_pendiente(resumen, actor, motivo or "Validación de marcaciones del trabajador.")
    return {"modificadas": modificadas, "completas": completas, "pendientes": pendientes, "cerradas": cerradas}
