import csv
import json
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Min, Max
from django.http import HttpResponse, HttpResponseForbidden
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from core.models import Usuario

# Sedes operativas; los textos libres de cuentas antiguas no son nuevas sedes.
SEDES_OPERATIVAS = ("CAJAMARCA", "CHICLAYO", "GACELA", "JAEN", "PAUL HARRIS", "TRUJILLO")

from asistencia.models import (
    ResumenAsistenciaDiaria, MarcacionBiometrica, TurnoHorario, CargaArchivoAsistencia,
    IncidenciaAsistencia, AjusteAsistencia, CorreccionEvento, CierreAsistencia,
    IdentidadBiometrica, FilaImportacionBiometrica,
)
from asistencia.services.revision import (
    puede_gestionar, puede_aprobar, comprobar_abierto, detalle_jornada,
    valores_ajustados, estado_revision, registrar_historial, dejar_pendiente, revisar,
)


def queryset_visible(usuario):
    qs = ResumenAsistenciaDiaria.objects.select_related("usuario__turno", "trabajador__usuario__turno", "turno_aplicado", "revisado_por").prefetch_related("incidencias", "ajustes", "trabajador__identidades")
    return qs if puede_gestionar(usuario) else qs.filter(Q(usuario=usuario) | Q(trabajador__usuario=usuario))


def filtros_asistencia(request):
    hoy = timezone.localdate()
    primer_dia = hoy.replace(day=1)
    ultimo_dia = hoy.replace(day=monthrange(hoy.year, hoy.month)[1])
    error = ""
    try:
        inicio = date.fromisoformat(request.GET.get("desde") or primer_dia.isoformat())
        fin = date.fromisoformat(request.GET.get("hasta") or ultimo_dia.isoformat())
        if fin < inicio:
            raise ValueError
    except ValueError:
        inicio, fin = primer_dia, ultimo_dia
        error = "El intervalo de fechas no es válido. Se muestra el mes actual."
    return {
        "desde": inicio.isoformat(), "hasta": fin.isoformat(), "sede": request.GET.get("sede", ""),
        "trabajador": request.GET.get("trabajador", "").strip(), "estado": request.GET.get("estado", ""),
        "revision": request.GET.get("revision", ""), "area": request.GET.get("area", "").strip(), "error": error,
    }


def reporte_filtrado(request):
    f = filtros_asistencia(request)
    qs = queryset_visible(request.user).filter(fecha__range=(f["desde"], f["hasta"]))
    if f["sede"]:
        qs = qs.filter(Q(trabajador__sede=f["sede"]) | Q(trabajador__isnull=True, usuario__agencia_sede=f["sede"]))
    if f["trabajador"]:
        term = f["trabajador"]
        for palabra in term.split():
            qs = qs.filter(Q(usuario__dni__icontains=palabra) | Q(usuario__first_name__icontains=palabra) | Q(usuario__last_name__icontains=palabra) | Q(trabajador__dni__icontains=palabra) | Q(trabajador__nombre_completo__icontains=palabra))
    if f["estado"]:
        qs = qs.filter(estado=f["estado"])
    if f["area"]:
        area = Q(trabajador__area__iexact=f["area"])
        if f["area"].casefold() == "por completar":
            area |= Q(trabajador__isnull=True) | Q(trabajador__area="")
        qs = qs.filter(area)
    if f["revision"] == "APROBADO":
        qs = qs.filter(verificado_contabilidad=True)
    elif f["revision"] in {"PENDIENTE", "OBSERVADO"}:
        qs = qs.filter(verificado_contabilidad=False, estado_revision=f["revision"])
    return f, qs.order_by("-fecha", "usuario__last_name", "pk")


def consolidar(resumenes):
    personas = {}
    for r in resumenes:
        fila = personas.setdefault(r.persona.dni, {
            "usuario": r.persona, "jornadas": 0, "aprobadas": 0, "pendientes": 0,
            "observadas": 0, "tardanza": 0, "ajustes": 0,
            **{k: Decimal(0) for k, _ in AjusteAsistencia.CONCEPTOS},
        })
        fila["jornadas"] += 1
        revision = estado_revision(r)
        fila[{"APROBADO": "aprobadas", "OBSERVADO": "observadas", "PENDIENTE": "pendientes"}[revision]] += 1
        fila["tardanza"] += r.minutos_tardanza
        fila["ajustes"] += len(r.ajustes.all())
        for key, val in valores_ajustados(r).items():
            fila[key] += val
    return list(personas.values())


def contexto_asistencia(request):
    if request.GET.get('vista') == 'asistencia' and request.GET.get('detalle', '').isdigit():
        from asistencia.services.carga_detalle import contexto_detalle_rapido
        return contexto_detalle_rapido(request)
    filtros, qs = reporte_filtrado(request)
    resumenes = list(qs)
    conteos = {s: 0 for s in ("APROBADO", "PENDIENTE", "OBSERVADO")}
    for r in resumenes:
        r.revision_visible = estado_revision(r)
        r.turno_visible = r.turno_aplicado or r.persona.turno
        r.valores = valores_ajustados(r)
        conteos[r.revision_visible] += 1
    pagina = Paginator(resumenes, 30).get_page(request.GET.get("pagina"))
    grupos = consolidar(resumenes)
    grupos.sort(key=lambda fila: fila["usuario"].nombre_completo.casefold())
    for fila in grupos:
        persona = fila["usuario"]
        fila["area"] = getattr(persona, "area", "Por completar")
        fila["codigo"] = persona.codigo if hasattr(persona, "codigo") else (persona.zkteco_user_id or "Sin código vinculado")
    pagina_trabajadores = Paginator(grupos, 20).get_page(request.GET.get("pagina"))
    from asistencia.services.revision_trabajador import detalles_en_lote, dia_validado
    filas_visibles = {fila["usuario"].dni: fila for fila in pagina_trabajadores}
    for fila in filas_visibles.values():
        fila["validadas"] = 0
        fila["por_aprobar"] = fila["jornadas"] - fila["aprobadas"]
    # Al navegar un día solo se reconstruye el trabajador abierto, no toda la sede.
    resumen_abierto = None
    if request.GET.get('detalle', '').isdigit():
        resumen_abierto = get_object_or_404(queryset_visible(request.user), pk=int(request.GET['detalle']))
    jornadas_detalle = [r for r in resumenes if r.persona.dni == resumen_abierto.persona.dni] if resumen_abierto else (resumenes if puede_gestionar(request.user) else [r for r in resumenes if r.persona.dni in filas_visibles])
    detalles_dashboard = detalles_en_lote(jornadas_detalle)
    from asistencia.services.tiempo_faltante import agregar_tiempo_faltante
    total_tiempo_faltante = agregar_tiempo_faltante(grupos, detalles_dashboard)
    for d in detalles_dashboard:
        if d["resumen"].persona.dni in filas_visibles:
            filas_visibles[d["resumen"].persona.dni]["validadas"] += int(dia_validado(d))
    for fila in filas_visibles.values():
        fila["sin_validar"] = fila["jornadas"] - fila["validadas"]
    visibles = Usuario.objects.select_related('ficha_trabajador').all() if puede_gestionar(request.user) else Usuario.objects.select_related('ficha_trabajador').filter(pk=request.user.pk)
    query = {k: v for k, v in filtros.items() if k != "error" and v}
    query["vista"] = "asistencia"
    detalle = None
    dni_ventana = request.GET.get("persona_dni", "")
    if request.GET.get("detalle", "").isdigit():
        r = resumen_abierto
        detalle = detalle_jornada(r)
        from asistencia.services.reglas_jornada import calendario_especial
        especial = calendario_especial(r.fecha, r.fecha).get(r.fecha, '')
        semana = r.fecha.weekday()
        detalle['calendario_dia'] = {
            'dia': ('Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo')[semana],
            'clase': 'feriado' if especial else 'sabado' if semana == 5 else 'domingo' if semana == 6 else 'normal',
            'feriado': especial,
        }
        if not dni_ventana:
            dni_ventana = r.persona.dni
    revision_trabajador = None
    seleccionadas = []
    if dni_ventana:
        from asistencia.services.revision_trabajador import filtrar_persona, contexto_revision
        seleccionadas = list(filtrar_persona(queryset_visible(request.user), dni_ventana).filter(fecha__range=(filtros["desde"], filtros["hasta"])).order_by("fecha", "pk"))
        if not seleccionadas:
            from django.http import Http404
            raise Http404("El trabajador no tiene jornadas disponibles en este periodo.")
        detalles_por_pk = {d['resumen'].pk: d for d in detalles_dashboard}
        reutilizables = [detalles_por_pk[s.pk] for s in seleccionadas] if all(s.pk in detalles_por_pk for s in seleccionadas) else None
        revision_trabajador = contexto_revision(seleccionadas, date.fromisoformat(filtros["desde"]), date.fromisoformat(filtros["hasta"]), detalles=reutilizables)
        ultimo = request.session.get("resultado_aprobacion_masiva", {})
        if ultimo.get("dni") == dni_ventana and ultimo.get("desde") == filtros["desde"] and ultimo.get("hasta") == filtros["hasta"]:
            revision_trabajador["resultado_aprobacion"] = ultimo
        dnis_trabajadores = [fila["usuario"].dni for fila in grupos]
        if dni_ventana in dnis_trabajadores:
            idx_w = dnis_trabajadores.index(dni_ventana)
            trabajador_ant = grupos[idx_w - 1]["usuario"] if idx_w > 0 else None
            trabajador_sig = grupos[idx_w + 1]["usuario"] if idx_w < len(dnis_trabajadores) - 1 else None
            revision_trabajador["anterior_dni"] = trabajador_ant.dni if trabajador_ant else None
            revision_trabajador["anterior_nombre"] = trabajador_ant.nombre_corto if trabajador_ant else None
            revision_trabajador["siguiente_dni"] = trabajador_sig.dni if trabajador_sig else None
            revision_trabajador["siguiente_nombre"] = trabajador_sig.nombre_corto if trabajador_sig else None
            revision_trabajador["posicion_indice"] = idx_w + 1
            revision_trabajador["total_trabajadores"] = len(dnis_trabajadores)
    if detalle and seleccionadas:
        pks_dias = [s.pk for s in seleccionadas]
        if r.pk in pks_dias:
            inicio_nav = date.fromisoformat(filtros['desde'])
            fin_nav = date.fromisoformat(filtros['hasta'])
            fecha_ant = r.fecha - timedelta(days=1) if r.fecha > inicio_nav else None
            fecha_sig = r.fecha + timedelta(days=1) if r.fecha < fin_nav else None
            por_fecha = {s.fecha: s for s in seleccionadas}
            from asistencia.models import PeriodoVacaciones
            vacaciones = list(PeriodoVacaciones.objects.filter(trabajador_id=r.trabajador_id, desde__lte=fin_nav, hasta__gte=inicio_nav)) if r.trabajador_id else []
            omitidas = {s.fecha for s in seleccionadas if s.verificado_contabilidad and s.estado == 'VACACIONES' and any(v.aprobado_el and v.desde <= s.fecha <= v.hasta for v in vacaciones)}
            omitidas.update(s.fecha for s in seleccionadas if s.verificado_contabilidad and s.estado == 'DIA_LIBRE' and s.conceptos_editados.get('descanso_validado_programacion'))
            while fecha_ant in omitidas:
                fecha_ant -= timedelta(days=1)
            while fecha_sig in omitidas:
                fecha_sig += timedelta(days=1)
            if fecha_ant and fecha_ant < inicio_nav:
                fecha_ant = None
            if fecha_sig and fecha_sig > fin_nav:
                fecha_sig = None
            detalle['periodo_vacaciones'] = next((v for v in vacaciones if v.desde <= r.fecha <= v.hasta), None)
            dia_ant = por_fecha.get(fecha_ant)
            dia_sig = por_fecha.get(fecha_sig)
            detalle["anterior_pk"] = dia_ant.pk if dia_ant else None
            detalle["anterior_fecha"] = fecha_ant
            detalle["siguiente_pk"] = dia_sig.pk if dia_sig else None
            detalle["siguiente_fecha"] = fecha_sig
            detalle["posicion_indice"] = (r.fecha - inicio_nav).days + 1
            detalle["total_dias"] = (fin_nav - inicio_nav).days + 1
    from django.conf import settings
    if getattr(settings,'MOVIL_HABILITADO',True) and detalle and puede_gestionar(request.user):
        from movil.models import Registro
        r=detalle['resumen']
        detalle['marcas_moviles_pendientes']=Registro.objects.filter(perfil__trabajador_id=r.trabajador_id,jornada=r.fecha,estado='POR_REVISAR') if r.trabajador_id else []
    inicio, fin = filtros["desde"], filtros["hasta"]
    marcas = MarcacionBiometrica.objects.filter(fecha_hora__date__range=(inicio, fin))
    if not puede_gestionar(request.user):
        marcas = marcas.filter(usuario=request.user)
    sin_identidad = marcas.filter(usuario__isnull=True, identidad_biometrica__isnull=True).order_by("fecha_hora")
    if filtros["sede"] or filtros["trabajador"]:
        # Las marcas sin identidad aún no tienen una sede o trabajador confiables.
        sin_identidad_visible = []
    else:
        sin_identidad_visible = list(sin_identidad[:30])
    totales = {k: sum((r.valores[k] for r in resumenes), Decimal(0)) for k, _ in AjusteAsistencia.CONCEPTOS}
    identidad_consultada = None
    marcas_codigo = []
    filtros_codigos = {campo: request.GET.get(campo, "").strip()[:150] for campo in ("sede_codigo", "filtro_codigo", "nombre_codigo")}
    from asistencia.services.grupos_importacion import grupo_importacion
    es_importador = request.GET.get('vista') == 'excel-zk'
    grupo = grupo_importacion(request.GET) if puede_gestionar(request.user) and es_importador else None
    if grupo:
        filtros_codigos.update(grupo_mes=grupo['mes'], grupo_carga=grupo['carga_id'])
    identidades = IdentidadBiometrica.objects.select_related("usuario", "trabajador").all() if puede_gestionar(request.user) and es_importador else IdentidadBiometrica.objects.none()
    if grupo and grupo['activo']:
        identidades = identidades.filter(
            Q(pk__in=grupo['marcas'].values('identidad_biometrica_id')) |
            Q(pk__in=FilaImportacionBiometrica.objects.filter(marcacion__in=grupo['marcas']).values('identidad_id'))
        )
    sedes_codigos = SEDES_OPERATIVAS
    if filtros_codigos["sede_codigo"]:
        identidades = identidades.filter(sede=filtros_codigos["sede_codigo"])
    if filtros_codigos["filtro_codigo"]:
        identidades = identidades.filter(codigo__icontains=filtros_codigos["filtro_codigo"])
    for termino in filtros_codigos["nombre_codigo"].split():
        identidades = identidades.filter(Q(nombre__icontains=termino) | Q(trabajador__nombre_completo__icontains=termino))
    total_identificacion = identidades.count()
    pendientes_identificacion = identidades.filter(trabajador__isnull=True).count()
    estado_identificacion = request.GET.get('identificacion', 'todos')
    if estado_identificacion not in {'todos','pendientes','identificados'}:
        estado_identificacion = 'todos'
    filtros_codigos['identificacion'] = estado_identificacion
    enlaces_identificacion = []
    for clave, etiqueta, cantidad in [('todos','Todos',total_identificacion),('pendientes','Pendientes de identificar',pendientes_identificacion),('identificados','Identificados',total_identificacion-pendientes_identificacion)]:
        enlaces_identificacion.append({'estado':clave,'nombre':etiqueta,'total':cantidad,
            'url':'?' + urlencode({'vista':'excel-zk',**filtros_codigos,'identificacion':clave}) + '#lista-codigos-huellero'})
    if estado_identificacion == 'pendientes':
        identidades = identidades.filter(trabajador__isnull=True)
    elif estado_identificacion == 'identificados':
        identidades = identidades.filter(trabajador__isnull=False)
    identificados = identidades.exclude(trabajador__isnull=True)
    marcas_envio = MarcacionBiometrica.objects.filter(Q(identidad_biometrica__in=identificados) | Q(filas_origen__identidad__in=identificados))
    if grupo and grupo['activo']:
        marcas_envio = marcas_envio.filter(pk__in=grupo['marcas'])
    periodo_envio = marcas_envio.aggregate(desde=Min("fecha_hora"), hasta=Max("fecha_hora"))
    if puede_gestionar(request.user) and request.GET.get("codigo_biometrico", "").isdigit():
        identidad_consultada = get_object_or_404(identidades, pk=int(request.GET["codigo_biometrico"]))
        marcas_consultadas = MarcacionBiometrica.objects.filter(Q(identidad_biometrica=identidad_consultada) | Q(filas_origen__identidad=identidad_consultada))
        if grupo and grupo['activo']:
            marcas_consultadas = marcas_consultadas.filter(pk__in=grupo['marcas'])
        marcas_codigo = marcas_consultadas.distinct().select_related("carga_origen").prefetch_related("filas_origen").order_by("fecha_hora")[:100]
    cierres_periodo = list(CierreAsistencia.objects.filter(fecha_inicio__lte=fin, fecha_fin__gte=inicio)) if puede_gestionar(request.user) else []
    from asistencia.services.dashboard_contable import resumen_dashboard
    dashboard_contable = resumen_dashboard(detalles_dashboard, filtros, cierres_periodo) if puede_gestionar(request.user) and request.GET.get('vista', 'dashboard') == 'dashboard' else None
    return {
        "dashboard_contable": dashboard_contable,
        "total_tiempo_faltante": total_tiempo_faltante,
        "filtros": filtros, "pagina_asistencia": pagina, "consulta_asistencia": urlencode(query),
        "detalle_jornada": detalle, "consolidado": grupos, "conteos_revision": conteos,
        "pagina_trabajadores": pagina_trabajadores, "total_trabajadores_asistencia": len(grupos),
        "revision_trabajador": revision_trabajador,
        "total_jornadas": len(resumenes), "totales_asistencia": totales,
        "total_vueltas": sum(r.total_vueltas_num for r in resumenes),
        "sedes_asistencia": SEDES_OPERATIVAS,
        "areas_asistencia": sorted({area or "Por completar" for area in queryset_visible(request.user).values_list("trabajador__area", flat=True)}, key=str.casefold),
        "estados_asistencia": ResumenAsistenciaDiaria.EstadoAsistencia.choices,
        "tipos_incidencia": IncidenciaAsistencia.TIPOS, "conceptos_ajuste": AjusteAsistencia.CONCEPTOS,
        "tipos_evento": MarcacionBiometrica.TipoEvento.choices,
        "puede_gestionar": puede_gestionar(request.user), "puede_aprobar": puede_aprobar(request.user),
        "sin_identidad": sin_identidad_visible, "total_sin_identidad": sin_identidad.count(),
        "usuarios_asistencia": visibles.filter(esta_activo=True, is_active=True),
        "cargas_con_error": CargaArchivoAsistencia.objects.filter(estado="ERROR").order_by("-fecha_subida")[:10] if puede_gestionar(request.user) else [],
        "cierres_asistencia": cierres_periodo,
        "jornadas_fecha_futura": queryset_visible(request.user).filter(fecha__gt=timezone.localdate()).count(),
        "identidades_biometricas": identidades[:200], "enlaces_identificacion": enlaces_identificacion,
        "grupo_importacion": grupo,
        "filtros_codigos": filtros_codigos, "sedes_codigos": sedes_codigos,
        "total_codigos_filtrados": identidades.count(),
        "consulta_codigos": urlencode({"vista": "excel-zk", **{k: v for k, v in filtros_codigos.items() if v}}),
        "total_identificados_envio": identificados.values("trabajador_id").distinct().count(),
        "desde_envio": timezone.localtime(periodo_envio["desde"]).date().isoformat() if periodo_envio["desde"] else "",
        "hasta_envio": timezone.localtime(periodo_envio["hasta"]).date().isoformat() if periodo_envio["hasta"] else "",
        "identidad_consultada": identidad_consultada,
        "marcas_codigo": marcas_codigo,
    }


def volver(request, resumen_id=None):
    # Construir la redirección con parámetros conocidos; no aceptar URLs externas.
    parametros = {k: request.POST[k] for k in ("desde", "hasta", "sede", "trabajador", "estado", "revision", "area") if request.POST.get(k)}
    parametros["vista"] = "asistencia"
    if resumen_id and (request.POST.get("solo_situacion") != "si" or request.POST.get('mantener_detalle') == 'si'):
        parametros["detalle"] = resumen_id
    if request.POST.get("persona_dni"):
        parametros["persona_dni"] = request.POST["persona_dni"][:20]
    return redirect(reverse("dashboard") + "?" + urlencode(parametros))


@login_required
@require_POST
def accion_jornada(request, resumen_id):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden("No tiene permiso para gestionar asistencia.")
    try:
        with transaction.atomic():
            r = get_object_or_404(queryset_visible(request.user).select_for_update(of=('self',)), pk=resumen_id)
            comprobar_abierto(r.fecha)
            accion = request.POST.get("accion")
            motivo = request.POST.get("motivo", "").strip()
            if accion == 'observacion_dia':
                texto = request.POST.get('observacion_dia', '').strip()
                if len(texto) > 3000:
                    raise ValidationError('La observación admite hasta 3000 caracteres.')
                if texto != r.observacion_dia:
                    registrar_historial(r, request.user, 'Observación del día', f'Antes: {r.observacion_dia}. Ahora: {texto}.')
                    r.observacion_dia = texto
                    r.save(update_fields=['observacion_dia'])
                messages.success(request, 'Observación del día guardada.')
            elif accion == 'configurar_nocturnas':
                if not r.trabajador_id:
                    raise ValidationError('Vincule la cuenta a una ficha de trabajador antes de configurar las nocturnas.')
                from asistencia.services.configuracion_nocturnas import configurar_nocturnas
                cantidad = configurar_nocturnas(r.trabajador, request.POST.get('calcular_nocturnas') == 'si', request.user)
                messages.success(request, f'Configuración de nocturnas guardada. {cantidad} jornadas pendientes actualizadas.')
            elif accion == 'validar_descansos':
                from datetime import date
                from asistencia.services.validacion_descansos import validar_descansos
                if not r.trabajador_id:
                    raise ValidationError('Vincule el trabajador antes de validar descansos.')
                try:
                    desde = date.fromisoformat(request.POST.get('desde', ''))
                    hasta = date.fromisoformat(request.POST.get('hasta', ''))
                except ValueError:
                    raise ValidationError('Seleccione un periodo válido para validar descansos.')
                cantidad, omitidas = validar_descansos(r.trabajador, desde, hasta, request.user)
                messages.success(request, f'{cantidad} días programados validados. {omitidas} días con registros o revisión previa conservados.')
            elif accion == 'validar_vacaciones':
                from asistencia.models import PeriodoVacaciones
                from asistencia.services.vacaciones import validar_vacaciones
                periodo = get_object_or_404(PeriodoVacaciones, pk=request.POST.get('periodo_id'), trabajador_id=r.trabajador_id)
                validar_vacaciones(periodo, request.user)
                messages.success(request, 'Vacaciones validadas. La navegación omitirá las fechas aprobadas del periodo.')
            elif accion == 'confirmar_descanso_trabajado':
                from asistencia.services.descanso_trabajado import confirmar_descanso_trabajado
                confirmar_descanso_trabajado(r, request.POST.get('tipo_descanso'), request.POST.get('fecha_descanso'), request.user)
                messages.success(request, 'Situación del descanso guardada. La jornada conserva su revisión pendiente.')
            elif accion == 'confirmar_feriado_trabajado':
                from asistencia.services.feriado_trabajado import confirmar_feriado_trabajado
                confirmar_feriado_trabajado(r, request.user)
                messages.success(request, 'Feriado trabajado confirmado: 08:00:00 adicionales registradas.')
            elif accion == 'aprobar_dia_situacion':
                from asistencia.services.aprobacion_situacion import aprobar_situacion_del_dia
                aprobar_situacion_del_dia(r, request.user, request.POST.get('tipo',''), motivo)
            elif accion in {"APROBADO", "OBSERVADO"}:
                revisar(r, request.user, accion, motivo)
            elif accion == "reabrir":
                dejar_pendiente(r, request.user, "Jornada reabierta para revisión y edición de datos.")
            elif accion in {'confirmar_refrigerio', 'retirar_refrigerio'}:
                if r.verificado_contabilidad:
                    raise ValidationError('Reabra la jornada antes de cambiar el refrigerio.')
                if not motivo:
                    raise ValidationError('Indique el motivo de la confirmación del refrigerio.')
                from asistencia.services.reglas_jornada import regla_resumen
                from asistencia.services.cuadro_excel import segundos_nocturnos
                detalle = detalle_jornada(r, incluir_formulario=False)
                conceptos = dict(r.conceptos_editados)
                if accion == 'confirmar_refrigerio':
                    regla = regla_resumen(r)
                    if not detalle['falta_refrigerio'] or not regla:
                        raise ValidationError('La jornada no tiene un refrigerio pendiente de confirmar.')
                    if segundos_nocturnos(detalle['tramos']):
                        raise ValidationError('En trabajo nocturno registre las horas reales del refrigerio para calcular correctamente la nocturnidad.')
                    conceptos['refrigerio_confirmado'] = regla.minutos_refrigerio * 60
                else:
                    conceptos.pop('refrigerio_confirmado', None)
                registrar_historial(r, request.user, 'Refrigerio confirmado' if accion == 'confirmar_refrigerio' else 'Refrigerio retirado',
                                    f'Antes: {r.conceptos_editados}. Ahora: {conceptos}. {motivo}')
                r.conceptos_editados = conceptos
                r.save(update_fields=['conceptos_editados'])
                dejar_pendiente(r, request.user, motivo)
                from asistencia.services.revision_trabajador import validar_periodo
                validar_periodo([r], {}, {}, None, motivo, request.user)
            elif accion == "turno":
                turno = get_object_or_404(TurnoHorario, pk=request.POST.get("turno"), activo=True)
                if r.trabajador_id:
                    from asistencia.services.horarios import programar_horarios
                    programar_horarios(r.trabajador, r.fecha, r.fecha, [r.fecha.weekday()], turno, motivo or 'Horario confirmado desde el detalle de la jornada.', request.user)
                else:
                    from asistencia.services.horarios import actualizar_tardanza
                    r.turno_aplicado = turno
                    r.save(update_fields=["turno_aplicado"])
                    actualizar_tardanza(r)
                    dejar_pendiente(r, request.user, f"Turno de la jornada: {turno.nombre}")
            elif accion == "incidencia":
                if not motivo:
                    raise ValidationError("Indique el motivo de la incidencia.")
                incidencia = IncidenciaAsistencia(
                    resumen=r, tipo=request.POST.get("tipo"), motivo=motivo,
                    minutos=request.POST.get("minutos") or None,
                    evidencia_url=request.POST.get("evidencia_url", "").strip(), creado_por=request.user,
                )
                incidencia.full_clean()
                incidencia.save()
                dejar_pendiente(r, request.user, "Incidencia registrada: " + incidencia.get_tipo_display())
            elif accion == "justificar_dia":
                detalle = detalle_jornada(r, incluir_formulario=False)
                situacion = detalle["situacion_dia"]
                if not situacion or situacion.tipo != "OTRO" or r.verificado_contabilidad:
                    raise ValidationError("Solo puede completar un día no trabajado pendiente de justificar.")
                tipos = {"DESCANSO_SEMANAL", "FERIADO_NO_LABORADO", "VACACIONES", "PERMISO", "DESCANSO_MEDICO", "CAMBIO_DESCANSO", "NO_LABORO", "CUMPLEANOS"}
                tipo = request.POST.get("tipo", "")
                if tipo not in tipos:
                    raise ValidationError("Seleccione la situación real del día.")
                if tipo == "PERMISO" and not motivo:
                    raise ValidationError("Indique la justificación del permiso.")
                if tipo != "PERMISO":
                    motivo = dict(IncidenciaAsistencia.TIPOS)[tipo]
                anterior = f"{situacion.get_tipo_display()}: {situacion.motivo}. Aprobación anterior: {situacion.aprobado_el or 'pendiente'}"
                situacion.tipo, situacion.motivo = tipo, motivo
                situacion.aprobado_por = situacion.aprobado_el = None
                situacion.full_clean()
                situacion.save(update_fields=["tipo", "motivo", "aprobado_por", "aprobado_el"])
                r.estado = "POR_REVISAR"
                r.save(update_fields=["estado"])
                dejar_pendiente(r, request.user, f"Situación del día corregida. Antes: {anterior}. Ahora: {situacion.get_tipo_display()}: {motivo}. Requiere nueva aprobación.")
            elif accion in {'editar_conceptos', 'restaurar_conceptos'}:
                if not puede_aprobar(request.user):
                    return HttpResponseForbidden('La edición corresponde a Contabilidad o Gerencia.')
                from asistencia.services.edicion_conceptos import guardar_conceptos
                if not detalle_jornada(r, incluir_formulario=False)['completa']:
                    raise ValidationError('Complete y valide las marcaciones antes de editar los tiempos.')
                if accion == 'restaurar_conceptos':
                    if r.verificado_contabilidad:
                        raise ValidationError('Reabra la jornada antes de restaurar sus tiempos.')
                    registrar_historial(r, request.user, 'Conceptos originales restaurados', str(r.conceptos_editados))
                    adicionales = list(r.ajustes.filter(concepto='descanso_feriado').values())
                    if adicionales:
                        registrar_historial(r, request.user, 'Adicional de feriado o descanso retirado', str(adicionales))
                        r.ajustes.filter(concepto='descanso_feriado').delete()
                        getattr(r, '_prefetched_objects_cache', {}).pop('ajustes', None)
                    r.conceptos_editados = {}
                    r.save(update_fields=['conceptos_editados'])
                else:
                    guardar_conceptos(r, request.POST, request.user)
                from asistencia.services.revision_trabajador import validar_periodo
                validar_periodo([r], {}, {}, None, 'Actualización de conceptos diarios.', request.user)
            elif accion == "ajuste":
                if not motivo:
                    raise ValidationError("Indique el motivo del ajuste.")
                minutos = int(request.POST.get("minutos", "0"))
                if minutos == 0:
                    raise ValidationError("El ajuste debe tener una duración distinta de cero.")
                ajuste = AjusteAsistencia(
                    resumen=r, concepto=request.POST.get("concepto"), minutos=minutos,
                    motivo=motivo, fecha_origen=request.POST.get("fecha_origen") or None, creado_por=request.user,
                )
                ajuste.full_clean()
                ajuste.save()
                dejar_pendiente(r, request.user, f"Ajuste propuesto: {ajuste.get_concepto_display()}, {minutos} minutos. {motivo}")
            elif accion in {"aprobar_incidencia", "aprobar_ajuste"}:
                if not puede_aprobar(request.user):
                    return HttpResponseForbidden("La aprobación corresponde a Contabilidad o Gerencia.")
                model = IncidenciaAsistencia if accion == "aprobar_incidencia" else AjusteAsistencia
                obj = get_object_or_404(model, pk=request.POST.get("registro_id"), resumen=r, aprobado_el__isnull=True)
                if accion == "aprobar_incidencia" and obj.tipo == "OTRO" and obj.minutos is None and obj.motivo == "Día no trabajado pendiente de justificar":
                    raise ValidationError("Complete la justificación del día antes de aprobar la situación.")
                if accion == "aprobar_ajuste":
                    nuevo_total = valores_ajustados(r)[obj.concepto] + Decimal(obj.minutos) / Decimal(60)
                    if nuevo_total < 0:
                        raise ValidationError("El ajuste dejaría el concepto con un total negativo. Registre una propuesta corregida.")
                elif obj.tipo == "VACACIONES" and obj.minutos is None and r.horas_trabajadas > 0:
                    raise ValidationError("La jornada tiene horas trabajadas. Concilie ese tiempo antes de aprobar vacaciones de día completo.")
                obj.aprobado_por, obj.aprobado_el = request.user, timezone.now()
                obj.save(update_fields=["aprobado_por", "aprobado_el"])
                if accion == "aprobar_incidencia" and obj.minutos is None:
                    estados = {"CUMPLEANOS": "DIA_LIBRE", "VACACIONES": "VACACIONES", "PERMISO": "PERMISO", "DESCANSO_MEDICO": "DESCANSO_MEDICO", "CAMBIO_DESCANSO": "DIA_LIBRE", "DESCANSO_SEMANAL": "DIA_LIBRE", "FERIADO_NO_LABORADO": "FERIADO"}
                    if obj.tipo in estados:
                        r.estado = estados[obj.tipo]
                        r.save(update_fields=["estado"])
                dejar_pendiente(r, request.user, f"{obj.__class__.__name__} #{obj.pk} aprobado: {obj.motivo}")
            elif accion in {"marcacion_manual", "editar_marcacion_manual"}:
                from asistencia.services.marcacion_manual import agregar_marcacion_manual
                from asistencia.services.revision_trabajador import validar_periodo
                cambios = {int(k.removeprefix("evento_")): v for k, v in request.POST.items() if k.startswith("evento_")}
                originales = {int(k.removeprefix("original_")): v for k, v in request.POST.items() if k.startswith("original_")}
                if cambios:
                    validar_periodo([r], cambios, originales, None, "Clasificación junto al registro manual.", request.user)
                marca_editar = get_object_or_404(MarcacionBiometrica.objects.select_for_update(), pk=request.POST.get('marcacion_id')) if accion == 'editar_marcacion_manual' else None
                agregar_marcacion_manual(r, request.POST, request.user, marcacion=marca_editar)
            elif accion == "eliminar_marcacion_manual":
                marcacion_id = request.POST.get("marcacion_id")
                if not marcacion_id:
                    raise ValidationError("No se especificó la marcación a eliminar.")
                marca = get_object_or_404(MarcacionBiometrica, pk=marcacion_id)
                if marca.pk not in [m.pk for m in detalle_jornada(r)["marcas"]]:
                    raise ValidationError("La marcación no pertenece al intervalo de esta jornada.")
                if marca.origen != "SISTEMA_MANUAL":
                    raise ValidationError("Solo se pueden eliminar directamente marcaciones registradas de forma manual.")
                motivo = motivo or "Marcación manual eliminada por error."
                registrar_historial(
                    r, request.user, "Marcación manual eliminada",
                    f"{timezone.localtime(marca.fecha_hora).strftime('%d/%m/%Y %H:%M:%S')} — {marca.get_tipo_evento_display()}. {motivo}",
                )
                marca.delete()
                marcas_restantes = [m for m in detalle_jornada(r)["marcas"] if m.es_valida]
                if marcas_restantes:
                    r.primera_entrada = timezone.localtime(min(m.fecha_hora for m in marcas_restantes)).time()
                    r.ultima_salida = timezone.localtime(max(m.fecha_hora for m in marcas_restantes)).time() if len(marcas_restantes) > 1 else None
                else:
                    r.primera_entrada = None
                    r.ultima_salida = None
                r.save(update_fields=["primera_entrada", "ultima_salida"])
                dejar_pendiente(r, request.user, "Se eliminó una marcación manual; requiere revisión de la jornada.")
                from asistencia.services.revision_trabajador import validar_periodo
                validar_periodo([r], {}, {}, None, "Recalculado tras eliminar marcación manual.", request.user)
            elif accion in {'excluir_duplicada', 'restaurar_duplicada'}:
                from asistencia.services.duplicadas import revisar_duplicada
                revisar_duplicada(r, request.user, int(request.POST.get('marcacion_id', '')), restaurar=accion == 'restaurar_duplicada')
            elif accion == "corregir_eventos":
                from asistencia.services.revision_trabajador import validar_periodo
                cambios = {int(k.removeprefix("evento_")): v for k, v in request.POST.items() if k.startswith("evento_")}
                originales = {int(k.removeprefix("original_")): v for k, v in request.POST.items() if k.startswith("original_")}
                if not cambios:
                    raise ValidationError("No hay marcaciones disponibles para corregir.")
                validar_periodo([r], cambios, originales, None, motivo, request.user)
                if request.POST.get('editar_tiempos') == 'si' or 'jornada_base' in request.POST:
                    if not puede_aprobar(request.user):
                        raise ValidationError('La edición de tiempos corresponde a Contabilidad o Gerencia.')
                    if not detalle_jornada(r, incluir_formulario=False)['completa']:
                        raise ValidationError('Complete las marcaciones antes de editar los tiempos.')
                    from asistencia.services.edicion_conceptos import guardar_conceptos
                    guardar_conceptos(r, request.POST, request.user)
                    validar_periodo([r], {}, {}, None, 'Tiempos guardados junto a las correcciones.', request.user)
            elif accion == "corregir_evento":
                motivo = motivo or "Clasificación de marcación laboral."
                marca = get_object_or_404(MarcacionBiometrica, pk=request.POST.get("marcacion_id"))
                if marca.pk not in [m.pk for m in detalle_jornada(r)["marcas"]]:
                    raise ValidationError("La marcación no pertenece al intervalo de esta jornada.")
                evento = request.POST.get("tipo_evento")
                if evento not in MarcacionBiometrica.TipoEvento.values:
                    raise ValidationError("Tipo de evento no válido.")
                CorreccionEvento.objects.update_or_create(marcacion=marca, defaults={"tipo_evento": evento, "motivo": motivo, "responsable": request.user})
                dejar_pendiente(r, request.user, "Se registró una corrección de evento.")
                registrar_historial(r, request.user, "Tipo de evento corregido", f"Original: {marca.tipo_evento}; efectivo: {evento}. {motivo}", marca)
            else:
                raise ValidationError("Acción no válida.")
        messages.success(request, "Cambio guardado. Consulte el detalle y el historial de la jornada.")
    except (ValidationError, ValueError, TypeError) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Revise los campos del formulario.")
    return volver(request, resumen_id)


@login_required
@require_POST
def asociar_marcacion(request, marcacion_id):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden("No tiene permiso para asociar marcaciones.")
    try:
        with transaction.atomic():
            marca = get_object_or_404(MarcacionBiometrica.objects.select_for_update(), pk=marcacion_id, usuario__isnull=True)
            comprobar_abierto(timezone.localtime(marca.fecha_hora).date())
            usuario = get_object_or_404(Usuario, pk=request.POST.get("usuario"), esta_activo=True, is_active=True)
            motivo = request.POST.get("motivo", "").strip()
            if not motivo:
                raise ValidationError("Indique el motivo de la asociación.")
            marca.usuario = usuario
            marca.save(update_fields=["usuario"])
            registrar_historial(None, request.user, "Identidad asociada", f"Trabajador #{usuario.pk}. {motivo}", marca)
        messages.success(request, "Identidad asociada. La marca original conserva su DNI e identificador reportados.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return volver(request)


@login_required
def exportar_asistencia(request):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden("No tiene permiso para exportar el resumen contable.")
    f, qs = reporte_filtrado(request)
    if f["error"]:
        return HttpResponse(f["error"], status=400)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="asistencia_{f["desde"]}_{f["hasta"]}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["Desde", "Hasta", "Código", "Trabajador", "Sede", "Jornadas", "Horas efectivas", "Extras 25 %", "Extras 35 %", "Nocturnas", "Descanso/feriado", "Tiempo faltante (HH:MM:SS)", "Aprobadas", "Pendientes"])
    resumenes = list(qs)
    filas = consolidar(resumenes)
    from asistencia.services.revision_trabajador import detalles_en_lote
    from asistencia.services.tiempo_faltante import agregar_tiempo_faltante
    agregar_tiempo_faltante(filas, detalles_en_lote(resumenes))
    for fila in filas:
        u = fila["usuario"]
        def seguro(value):
            text = str(value)
            return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
        codigo = getattr(u, "codigo", "")
        if not codigo:
            codigos = IdentidadBiometrica.objects.filter(Q(usuario_id=u.pk) | Q(trabajador__usuario_id=u.pk)).values_list("codigo", flat=True)
            codigo = " / ".join(sorted(set(codigos))) or "Sin código importado"
        writer.writerow([f["desde"], f["hasta"], seguro(codigo), seguro(u.nombre_completo), seguro(u.agencia_sede), fila["jornadas"], *[f"{fila[k]:.2f}" for k in ("horas_trabajadas", "horas_extras_25", "horas_extras_35", "horas_nocturnas", "descanso_feriado")], fila["tiempo_faltante"], fila["aprobadas"], fila["pendientes"]])
    return response


@login_required
@require_POST
def cerrar_periodo(request):
    if not puede_aprobar(request.user):
        return HttpResponseForbidden("Solo Contabilidad o Gerencia puede cerrar periodos.")
    try:
        if request.POST.get("confirmar") != "si":
            raise ValidationError("Confirme que ha revisado el periodo completo antes de cerrarlo.")
        inicio, fin = date.fromisoformat(request.POST.get("desde", "")), date.fromisoformat(request.POST.get("hasta", ""))
        if fin < inicio or fin >= timezone.localdate():
            raise ValidationError("El periodo debe terminar antes de hoy y tener fechas en orden.")
        with transaction.atomic():
            if CierreAsistencia.objects.filter(fecha_inicio__lte=fin, fecha_fin__gte=inicio).exists():
                raise ValidationError("El intervalo se superpone con un periodo cerrado.")
            qs = list(queryset_visible(request.user).select_for_update(of=('self',)).filter(fecha__range=(inicio, fin)))
            if not qs or any(estado_revision(r) != "APROBADO" for r in qs):
                raise ValidationError("Debe haber jornadas y todas deben estar aprobadas para cerrar el periodo completo.")
            if MarcacionBiometrica.objects.filter(fecha_hora__date__range=(inicio, fin), usuario__isnull=True).exclude(Q(identidad_biometrica__trabajador__isnull=False) | Q(filas_origen__identidad__trabajador__isnull=False)).exists():
                raise ValidationError("Hay marcaciones sin trabajador asociado en el periodo.")
            if any(detalle_jornada(r)["bloqueos"] for r in qs):
                raise ValidationError("Hay jornadas con incidencias de cálculo sin resolver.")
            sin_resumen = MarcacionBiometrica.objects.filter(fecha_hora__date__range=(inicio, fin), es_valida=True)
            for marca in sin_resumen.select_related("usuario"):
                dia = timezone.localtime(marca.fecha_hora).date()
                if not any(marca.pk in [m.pk for m in detalle_jornada(r)["marcas"]] for r in qs):
                    raise ValidationError("Hay marcaciones del periodo sin una jornada revisada que las incluya.")
            snapshot = [{**{k: str(v) for k, v in valores_ajustados(r).items()}, "resumen_id": r.pk, "dni": r.persona.dni, "fecha": r.fecha.isoformat()} for r in qs]
            cierre = CierreAsistencia.objects.create(fecha_inicio=inicio, fecha_fin=fin, cerrado_por=request.user, total_jornadas=len(qs), resumen_cierre=snapshot)
            registrar_historial(None, request.user, "Periodo cerrado", f"Cierre #{cierre.pk}: {inicio} a {fin}; {len(qs)} jornadas.")
        messages.success(request, "Periodo completo cerrado. Se guardó una copia de sus resultados aprobados.")
    except (ValidationError, ValueError) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Las fechas del cierre no son válidas.")
    return volver(request)


def detalle_jornada_intervalo_contiene(resumen, fecha_hora):
    from asistencia.services.revision import ventana_jornada
    inicio, fin = ventana_jornada(resumen)
    return inicio <= fecha_hora <= fin


@login_required
@require_POST
def crear_jornada(request):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden("No tiene permiso para crear jornadas.")
    resumen = None
    try:
        with transaction.atomic():
            fecha = date.fromisoformat(request.POST.get("fecha", ""))
            comprobar_abierto(fecha)
            usuario = get_object_or_404(Usuario, pk=request.POST.get("usuario"), esta_activo=True)
            from asistencia.services.horarios import turno_programado
            resumen, nueva = ResumenAsistenciaDiaria.objects.get_or_create(usuario=usuario, fecha=fecha, defaults={"estado": "PERMISO", "turno_aplicado": turno_programado(usuario, fecha)})
            if nueva:
                registrar_historial(resumen, request.user, "Jornada creada", "Sin marcas ni horas; pendiente de documentar y revisar.")
                messages.success(request, "Jornada creada. Agregue la incidencia o revise las marcaciones.")
            else:
                messages.info(request, "La jornada ya existe. Se muestra su detalle.")
    except (ValueError, ValidationError) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Seleccione una fecha válida.")
    return volver(request, resumen.pk if resumen else None)


@login_required
@require_POST
def consultar_huellero(request):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden("No tiene permiso para consultar el equipo.")
    from asistencia.services.zkteco_live import ZKTecoLiveClient
    return JsonResponse(ZKTecoLiveClient().sincronizar_marcaciones_en_vivo())


def datos_registros_huellero(usuario):
    """Eventos recibidos del biométrico; la marca web no se presenta como huella."""
    qs = MarcacionBiometrica.objects.filter(
        fecha_hora__date=timezone.localdate(), es_valida=True,
        origen=MarcacionBiometrica.OrigenMarcacion.ZKTECO_EN_LINEA,
    ).select_related("usuario", "correccion_evento").order_by("-fecha_hora", "-pk")
    if not puede_gestionar(usuario):
        qs = qs.filter(usuario=usuario)
    total = qs.count()
    eventos = []
    for m in qs[:100]:
        correccion = getattr(m, "correccion_evento", None)
        tipo = correccion.tipo_evento if correccion else m.tipo_evento
        eventos.append({
            "id": m.pk, "dni": m.usuario.dni if m.usuario else m.dni,
            "nombre": m.usuario.nombre_corto if m.usuario else (m.identidad_biometrica.nombre_corto if m.identidad_biometrica_id else m.nombre_empleado) or "Por identificar",
            "fecha_hora": timezone.localtime(m.fecha_hora).strftime("%d/%m/%Y %H:%M:%S"),
            "evento": dict(MarcacionBiometrica.TipoEvento.choices).get(tipo, tipo),
            "sede": m.usuario.agencia_sede if m.usuario else "Por identificar",
            "equipo": m.dispositivo_ip or "Sin equipo registrado",
            "id_biometrico": str(m.zkteco_user_id) if m.zkteco_user_id is not None else "—",
        })
    return {"registros": eventos, "total": total, "limite": 100, "actualizado": timezone.localtime().strftime("%d/%m/%Y %H:%M:%S")}


@login_required
@require_GET
def registros_huellero(request):
    response = JsonResponse(datos_registros_huellero(request.user))
    response["Cache-Control"] = "no-store"
    return response


@login_required
@require_POST
def importar_excel_web(request):
    if not puede_gestionar(request.user):
        return JsonResponse({"detail": "No tiene permiso para importar archivos."}, status=403)
    archivo = request.FILES.get("file")
    if not archivo or not archivo.name.lower().endswith((".xlsx", ".xls")):
        return JsonResponse({"detail": "Seleccione un archivo Excel .xlsx o .xls."}, status=400)
    if request.POST.get('progreso') == 'si':
        from asistencia.services.progreso_importacion import respuesta_importacion
        return respuesta_importacion(archivo, request.user.pk)
    from asistencia.services.zkteco_parser import ZKTecoExcelParser
    try:
        with transaction.atomic():
            resultado = ZKTecoExcelParser(archivo, archivo.name, request.user).procesar()
        return JsonResponse(resultado)
    except ValidationError as exc:
        return JsonResponse({"detail": " ".join(exc.messages)}, status=400)
    except (ValueError, ImportError):
        return JsonResponse({"detail": "El libro no se pudo leer. Compruebe que sea una exportación Excel válida y que no esté protegido por contraseña."}, status=400)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Fallo al importar el archivo biométrico")
        return JsonResponse({"detail": "La importación se canceló sin guardar cambios. El error quedó registrado para revisión del administrador."}, status=500)


@login_required
@require_POST
def vincular_identidad(request, identidad_id):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden("No tiene permiso para vincular códigos biométricos.")
    try:
        with transaction.atomic():
            identidad = get_object_or_404(IdentidadBiometrica.objects.select_for_update(), pk=identidad_id)
            if identidad.trabajador_id:
                raise ValidationError("La identidad ya tiene una ficha de trabajador. Utilice la identificación por ficha de personal.")
            uid = request.POST.get("usuario", "")
            usuario = get_object_or_404(Usuario, pk=uid, esta_activo=True, is_active=True) if uid else None
            if identidad.usuario_id and (not usuario or usuario.pk != identidad.usuario_id):
                raise ValidationError("El código ya está vinculado. No se reasigna automáticamente para proteger su historial.")
            motivo = request.POST.get("motivo", "").strip()
            if not motivo:
                raise ValidationError("Indique el motivo o la referencia que confirma esta identidad.")
            nombre = request.POST.get("nombre", "").strip() or (usuario.nombre_completo if usuario else identidad.nombre)
            if len(nombre) > 150:
                raise ValidationError("El nombre admite hasta 150 caracteres.")
            marcas = list(MarcacionBiometrica.objects.filter(Q(identidad_biometrica=identidad) | Q(filas_origen__identidad=identidad)).distinct())
            for marca in marcas:
                comprobar_abierto(timezone.localtime(marca.fecha_hora).date())
                if usuario and marca.usuario_id and marca.usuario_id != usuario.pk:
                    raise ValidationError("Una marcación del código está vinculada a otro trabajador. Revise la procedencia antes de cambiarla.")
            identidad.nombre = nombre
            identidad.usuario = usuario
            identidad.save(update_fields=["nombre", "usuario"])
            jornadas = set()
            for marca in marcas:
                if usuario and not marca.usuario_id:
                    marca.usuario, marca.dni = usuario, usuario.dni
                    marca.save(update_fields=["usuario", "dni"])
                    jornadas.add(timezone.localtime(marca.fecha_hora).date())
            if usuario:
                from asistencia.services.zkteco_parser import asegurar_jornada
                for fecha in jornadas:
                    asegurar_jornada(usuario, fecha)
            registrar_historial(None, request.user, "Código biométrico identificado", f"{identidad.sede} / {identidad.equipo} / {identidad.codigo}: {nombre}. Usuario #{usuario.pk if usuario else 'sin cuenta'}. {motivo}")
        messages.success(request, "Identidad guardada. Las próximas cargas reconocerán este código en su sede y equipo.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    return redirect(reverse("dashboard") + "?vista=excel-zk")


@login_required
@require_POST
def marcar_web(request):
    from asistencia.api import registrar_marcacion
    from asistencia.schemas import MarcacionCreateSchema
    from ninja.errors import HttpError
    from pydantic import ValidationError as SchemaError
    if not request.user.esta_activo or not request.user.is_active:
        return JsonResponse({"detail": "La cuenta está inactiva."}, status=403)
    try:
        data = MarcacionCreateSchema(**json.loads(request.body))
        if data.origen != "KIOSKO_PIN":
            return JsonResponse({"detail": "El registro web debe indicar origen Kiosko (DNI)."}, status=400)
        request.auth = request.user
        with transaction.atomic():
            marca = registrar_marcacion(request, data)
        return JsonResponse({"id": marca.pk, "mensaje": "Marcación registrada. La jornada queda pendiente de revisión."})
    except HttpError as exc:
        return JsonResponse({"detail": str(exc)}, status=exc.status_code)
    except ValidationError as exc:
        return JsonResponse({"detail": " ".join(exc.messages)}, status=400)
    except (SchemaError, ValueError, TypeError):
        return JsonResponse({"detail": "Revise el DNI y el tipo de marcación."}, status=400)
