from datetime import date
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from asistencia.models import TurnoHorario, Trabajador, ResumenAsistenciaDiaria, MarcacionBiometrica, IncidenciaAsistencia
from core.models import Usuario
from asistencia.services.revision import puede_gestionar, puede_aprobar, comprobar_abierto, marcas_persona, registrar_historial
from django.utils import timezone
from asistencia.services.revision_trabajador import filtrar_persona, validar_periodo
from asistencia.views import queryset_visible


@login_required
@require_POST
def validar_marcaciones_trabajador(request):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden("No tiene permiso para clasificar marcaciones.")
    dni = request.POST.get("persona_dni", "").strip()[:20]
    parametros = {"vista": "asistencia", "persona_dni": dni}
    try:
        desde = date.fromisoformat(request.POST.get("desde", ""))
        hasta = date.fromisoformat(request.POST.get("hasta", ""))
        if hasta < desde:
            raise ValueError
        parametros.update(desde=desde.isoformat(), hasta=hasta.isoformat())
        cambios = {int(k.removeprefix("evento_")): v for k, v in request.POST.items() if k.startswith("evento_")}
        originales = {int(k.removeprefix("original_")): v for k, v in request.POST.items() if k.startswith("original_")}
        turno_id = request.POST.get("turno", "")
        turno = get_object_or_404(TurnoHorario, pk=turno_id, activo=True) if turno_id else None
        with transaction.atomic():
            jornadas = list(filtrar_persona(queryset_visible(request.user).select_for_update(of=("self",)), dni).filter(fecha__range=(desde, hasta)).order_by("pk"))
            if not jornadas:
                raise ValidationError("No hay jornadas disponibles para ese trabajador en el periodo.")
            resultado = validar_periodo(jornadas, cambios, originales, turno, request.POST.get("motivo", "").strip()[:500], request.user)
        messages.success(request, f"Clasificación guardada: {resultado['modificadas']} marcas modificadas. {resultado['completas']} jornadas listas para revisión contable, {resultado['pendientes']} pendientes de completar y {resultado['cerradas']} de periodos cerrados conservadas. No se aprobó ninguna jornada automáticamente.")
    except (ValueError, ValidationError) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Revise las fechas y los tipos de marcación enviados.")
    return redirect(reverse("dashboard") + "?" + urlencode(parametros))


@login_required
@require_POST
def aprobar_periodo_trabajador(request):
    if not puede_aprobar(request.user):
        return HttpResponseForbidden("Solo Contabilidad o Gerencia puede aprobar jornadas.")
    dni = request.POST.get("persona_dni", "").strip()[:20]
    parametros = {"vista": "asistencia", "persona_dni": dni}
    try:
        desde = date.fromisoformat(request.POST.get("desde", ""))
        hasta = date.fromisoformat(request.POST.get("hasta", ""))
        if hasta < desde:
            raise ValueError
        parametros.update(desde=desde.isoformat(), hasta=hasta.isoformat())
        if request.POST.get("confirmar_aprobacion") != "si":
            raise ValidationError("Confirme que revisó el periodo del trabajador antes de aprobar las jornadas listas.")
        from asistencia.services.aprobacion_masiva import aprobar_jornadas_listas
        with transaction.atomic():
            jornadas = list(filtrar_persona(queryset_visible(request.user).select_for_update(of=("self",)), dni).filter(fecha__range=(desde, hasta)).order_by("fecha", "pk"))
            if not jornadas:
                raise ValidationError("El trabajador no tiene jornadas disponibles en el periodo.")
            resultado = aprobar_jornadas_listas(jornadas, desde, hasta, request.user)
        request.session["resultado_aprobacion_masiva"] = {**resultado, "dni": dni, "desde": desde.isoformat(), "hasta": hasta.isoformat(), "registrado_el": timezone.localtime().isoformat()}
        messages.success(request, f"Aprobación conjunta: {resultado['aprobadas']} jornadas aprobadas, {resultado['ya_aprobadas']} ya estaban aprobadas y {len(resultado['pendientes'])} fechas siguen pendientes. Consulte los motivos en la ventana del trabajador.")
    except (ValueError, ValidationError) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Seleccione un periodo válido.")
    return redirect(reverse("dashboard") + "?" + urlencode(parametros))


@login_required
@require_POST
def registrar_trabajo_omitido(request):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden('No tiene permiso para registrar asistencia manual.')
    dni = request.POST.get('persona_dni', '').strip()[:20]
    parametros = {'vista': 'asistencia', 'persona_dni': dni}
    parametros.update({k: request.POST[k] for k in ('sede', 'area', 'trabajador', 'estado', 'revision') if request.POST.get(k)})
    try:
        desde = date.fromisoformat(request.POST.get('desde', ''))
        hasta = date.fromisoformat(request.POST.get('hasta', ''))
        fecha = date.fromisoformat(request.POST.get('fecha', ''))
        parametros.update(desde=desde.isoformat(), hasta=hasta.isoformat())
        if not desde <= fecha <= hasta:
            raise ValidationError('Seleccione un día del periodo consultado.')
        with transaction.atomic():
            fuente = filtrar_persona(queryset_visible(request.user), dni).filter(fecha__range=(desde, hasta)).first()
            if not fuente:
                raise ValidationError('El trabajador no está disponible en este periodo.')
            modelo, pk = (Trabajador, fuente.trabajador_id) if fuente.trabajador_id else (Usuario, fuente.usuario_id)
            modelo.objects.select_for_update().get(pk=pk)
            comprobar_abierto(fecha)
            resumen = filtrar_persona(queryset_visible(request.user), dni).select_for_update(of=('self',)).filter(fecha=fecha).first()
            if not resumen:
                resumen = ResumenAsistenciaDiaria.objects.create(trabajador_id=fuente.trabajador_id,
                    usuario_id=fuente.usuario_id, fecha=fecha, estado='POR_REVISAR', marcaciones_publicadas=[])
            from asistencia.services.dia_trabajado_manual import registrar_trabajo_omitido as registrar
            if request.POST.get('navegar_dia') == 'si':
                # Abrir un hueco del calendario no implica que haya trabajado ni sustituye su situación.
                pass
            elif request.POST.get('abrir_detalle') == 'si':
                from asistencia.services.revision import detalle_jornada, dejar_pendiente
                detalle = detalle_jornada(resumen, incluir_formulario=False)
                if resumen.verificado_contabilidad:
                    raise ValidationError('Reabra el día aprobado antes de registrar trabajo.')
                if (any(m.es_valida for m in detalle['marcas']) or resumen.ajustes.exists()
                        or MarcacionBiometrica.objects.filter(marcas_persona(resumen), fecha_hora__date=fecha, es_valida=True).exists()):
                    raise ValidationError('El día ya tiene marcaciones o ajustes. Ábralo desde Ver detalle.')
                situacion = detalle['situacion_dia']
                if situacion:
                    registrar_historial(resumen, request.user, 'Situación sustituida por trabajo sin marcar',
                        f'{situacion.get_tipo_display()}: {situacion.motivo}. Aprobación anterior: {situacion.aprobado_el or "pendiente"}. Se abrió el detalle para registrar las horas confirmadas.')
                    situacion.delete()
                resumen.estado = 'POR_REVISAR'
                resumen.marcaciones_publicadas = []
                resumen.save(update_fields=['estado', 'marcaciones_publicadas'])
                dejar_pendiente(resumen, request.user, 'Trabajó sin marcar. Pendiente de registrar y verificar las marcaciones manuales.')
            else:
                registrar(resumen, request.POST, request.user)
        parametros['detalle'] = resumen.pk
        if request.POST.get('abrir_detalle') != 'si' and request.POST.get('navegar_dia') != 'si':
            messages.success(request, 'Asistencia manual registrada. Revise las horas y el horario antes de aprobar el día.')
    except (ValueError, ValidationError) as exc:
        messages.error(request, ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'Seleccione fechas válidas.')
    return redirect(reverse('dashboard') + '?' + urlencode(parametros))


@login_required
@require_POST
def registrar_dia_sin_marcas(request):
    if not puede_gestionar(request.user):
        return HttpResponseForbidden("No tiene permiso para registrar días no laborados.")
    dni = request.POST.get("persona_dni", "").strip()[:20]
    parametros = {"vista": "asistencia", "persona_dni": dni}
    tipos = {"CUMPLEANOS": "Cumpleaños", "FERIADO_NO_LABORADO": "Feriado no laborado", "DESCANSO_SEMANAL": "Descanso semanal", "NO_LABORO": "No laboró", "NO_TRABAJO": "Día no trabajado pendiente de justificar", "VACACIONES": "Vacaciones", "PERMISO": "Permiso", "DESCANSO_MEDICO": "Descanso médico", "CAMBIO_DESCANSO": "Cambio de descanso"}
    try:
        desde, hasta = date.fromisoformat(request.POST.get("desde", "")), date.fromisoformat(request.POST.get("hasta", ""))
        fecha = date.fromisoformat(request.POST.get("fecha", ""))
        parametros.update(desde=desde.isoformat(), hasta=hasta.isoformat())
        tipo = request.POST.get("tipo_dia", "")
        if not desde <= fecha <= hasta or tipo not in tipos:
            raise ValidationError("Seleccione una fecha del periodo y una situación válida.")
        with transaction.atomic():
            fuente = filtrar_persona(queryset_visible(request.user), dni).filter(fecha__range=(desde, hasta)).first()
            if not fuente:
                raise ValidationError("El trabajador no está disponible para ese periodo.")
            modelo, pk = (Trabajador, fuente.trabajador_id) if fuente.trabajador_id else (Usuario, fuente.usuario_id)
            modelo.objects.select_for_update().get(pk=pk)
            comprobar_abierto(fecha)
            if filtrar_persona(queryset_visible(request.user), dni).filter(fecha=fecha).exists():
                raise ValidationError("Ese día ya tiene una jornada. Registre la situación desde su detalle.")
            if MarcacionBiometrica.objects.filter(marcas_persona(fuente), fecha_hora__date=fecha, es_valida=True).exists():
                raise ValidationError("Hay marcaciones para ese día. Revise o envíe esas marcas antes de registrar un día no laborado.")
            resumen = ResumenAsistenciaDiaria.objects.create(trabajador_id=fuente.trabajador_id, usuario_id=fuente.usuario_id, fecha=fecha, estado="POR_REVISAR", observaciones=tipos[tipo])
            IncidenciaAsistencia.objects.create(resumen=resumen, tipo="OTRO" if tipo == "NO_TRABAJO" else tipo, motivo=tipos[tipo], creado_por=request.user)
            registrar_historial(resumen, request.user, "Día sin marcaciones registrado", tipos[tipo] + ". Pendiente de aprobación; no se crearon marcaciones.")
        messages.success(request, "Situación del día registrada. Puede revisarla y aprobarla en la misma fila, sin abrir el detalle de marcaciones.")
    except (ValueError, ValidationError) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Seleccione fechas válidas.")
    return redirect(reverse("dashboard") + "?" + urlencode(parametros))
