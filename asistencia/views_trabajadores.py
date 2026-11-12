from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from asistencia.forms import TrabajadorForm
from asistencia.models import Trabajador, IdentidadBiometrica, MarcacionBiometrica, FilaImportacionBiometrica
from asistencia.services.revision import puede_gestionar, comprobar_abierto, registrar_historial
from django.utils import timezone
from asistencia.services.trabajadores import vincular_ficha, corregir_ficha_duplicada
from core.models import Usuario
from datetime import date
from urllib.parse import urlencode
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


def datos(trabajador):
    return {"id": trabajador.pk, "nombre": trabajador.nombre_corto, "nombre_completo": trabajador.nombre_completo,
            "nombres": trabajador.nombres, "apellido_paterno": trabajador.apellido_paterno, "apellido_materno": trabajador.apellido_materno,
            "dni": trabajador.dni, "codigo": trabajador.codigo, "area": trabajador.area,
            "url_editar": reverse('editar_ficha_trabajador', args=[trabajador.pk])}


@login_required
@require_GET
def sugerir_codigos(request):
    if not puede_gestionar(request.user):
        return JsonResponse({'detail':'No tiene permiso para consultar códigos.'}, status=403)
    consulta = request.GET.get('q', '').strip()[:60]
    if not consulta:
        return JsonResponse({'resultados':[]})
    from asistencia.services.grupos_importacion import grupo_importacion
    grupo = grupo_importacion(request.GET)
    identidades = IdentidadBiometrica.objects.select_related('trabajador').filter(codigo__icontains=consulta)
    if grupo['activo']:
        identidades = identidades.filter(Q(pk__in=grupo['marcas'].values('identidad_biometrica_id')) |
            Q(pk__in=FilaImportacionBiometrica.objects.filter(marcacion__in=grupo['marcas']).values('identidad_id')))
    sede = request.GET.get('sede_codigo', '').strip()[:100]
    if sede:
        identidades = identidades.filter(sede=sede)
    if request.GET.get('identificacion') == 'pendientes':
        identidades = identidades.filter(trabajador__isnull=True)
    elif request.GET.get('identificacion') == 'identificados':
        identidades = identidades.filter(trabajador__isnull=False)
    for termino in request.GET.get('nombre_codigo', '').strip()[:150].split():
        identidades = identidades.filter(Q(nombre__icontains=termino) | Q(trabajador__nombre_completo__icontains=termino))
    return JsonResponse({'resultados':[{'codigo':i.codigo, 'nombre':i.nombre_corto,
        'sede':i.sede, 'equipo':i.equipo} for i in identidades.order_by('codigo','sede','equipo')[:15]]})


@login_required
@require_GET
def buscar_trabajadores(request):
    if not puede_gestionar(request.user):
        return JsonResponse({"detail": "No tiene permiso para consultar trabajadores."}, status=403)
    consulta = request.GET.get("q", "").strip()[:100]
    if len(consulta) < 2:
        return JsonResponse({"resultados": [], "detail": "Escriba al menos 2 caracteres."})
    fichas = Trabajador.objects.prefetch_related("identidades")
    for termino in consulta.split():
        fichas = fichas.filter(Q(nombre_completo__icontains=termino) | Q(dni__icontains=termino) | Q(identidades__codigo__icontains=termino))
    return JsonResponse({"resultados": [datos(t) for t in fichas.distinct()[:20]]})


@login_required
@require_POST
def confirmar_trabajador(request, identidad_id):
    if not puede_gestionar(request.user):
        return JsonResponse({"detail": "No tiene permiso para identificar trabajadores."}, status=403)
    tid = request.POST.get("trabajador", "")
    if not tid.isdigit():
        return JsonResponse({"detail": "Seleccione un trabajador de los resultados."}, status=400)
    try:
        with transaction.atomic():
            identidad = get_object_or_404(IdentidadBiometrica.objects.select_for_update(), pk=identidad_id)
            trabajador = get_object_or_404(Trabajador, pk=tid)
            vincular_ficha(identidad, trabajador, request.user)
        return JsonResponse({"trabajador": datos(trabajador)})
    except ValidationError as exc:
        return JsonResponse({"detail": " ".join(exc.messages)}, status=400)


@login_required
@require_POST
def registrar_trabajador(request, identidad_id):
    if not puede_gestionar(request.user):
        return JsonResponse({"detail": "No tiene permiso para registrar trabajadores."}, status=403)
    formulario = TrabajadorForm(request.POST)
    if not formulario.is_valid():
        return JsonResponse({"detail": "Revise los datos del trabajador.", "errores": formulario.errors}, status=400)
    try:
        with transaction.atomic():
            identidad = get_object_or_404(IdentidadBiometrica.objects.select_for_update(), pk=identidad_id)
            trabajador = formulario.save(commit=False)
            trabajador.sede = identidad.sede
            trabajador.usuario = Usuario.objects.filter(dni=trabajador.dni).first()
            trabajador.save()
            vincular_ficha(identidad, trabajador, request.user)
        return JsonResponse({"trabajador": datos(trabajador)}, status=201)
    except ValidationError as exc:
        return JsonResponse({"detail": " ".join(exc.messages)}, status=400)
    except IntegrityError:
        return JsonResponse({"detail": "El documento ya está registrado. Busque al trabajador y selecciónelo."}, status=409)


@login_required
@require_POST
def editar_trabajador(request, identidad_id=None, trabajador_id=None):
    if not puede_gestionar(request.user):
        return JsonResponse({"detail": "No tiene permiso para editar trabajadores."}, status=403)
    try:
        with transaction.atomic():
            if identidad_id is not None:
                identidad = get_object_or_404(IdentidadBiometrica.objects.select_for_update(), pk=identidad_id)
                trabajador_id = identidad.trabajador_id
            trabajador = get_object_or_404(Trabajador.objects.select_for_update(), pk=trabajador_id)
            dni_propuesto = request.POST.get("dni", "").strip()
            existente = Trabajador.objects.select_for_update().filter(dni=dni_propuesto).exclude(pk=trabajador.pk).first()
            if existente:
                if request.POST.get("usar_existente") == "1":
                    if request.POST.get("destino_id") != str(existente.pk) or request.POST.get("origen_id") != str(trabajador.pk):
                        raise ValidationError("La identificación cambió. Cierre la ventana y vuelva a revisar los datos.")
                    corregir_ficha_duplicada(trabajador, existente, request.user)
                    return JsonResponse({"trabajador": datos(existente)})
                return JsonResponse({
                    "detail": "El DNI corresponde a una ficha existente. Confirme si ambas fichas son de la misma persona.",
                    "conflicto": {"destino": datos(existente), "origen_id": trabajador.pk, "codigos": trabajador.identidades.count(), "puede_unir": not bool(trabajador.usuario_id)},
                }, status=409)
            if request.POST.get("usar_existente") == "1":
                raise ValidationError("La ficha de destino ya no coincide. Vuelva a comprobar el DNI.")
            anterior = {campo: getattr(trabajador, campo) for campo in ("nombre_completo", "nombres", "apellido_paterno", "apellido_materno", "dni", "area")}
            formulario = TrabajadorForm(request.POST, instance=trabajador)
            if not formulario.is_valid():
                return JsonResponse({"detail": "Revise los datos del trabajador.", "errores": formulario.errors}, status=400)
            dni = formulario.cleaned_data["dni"]
            if trabajador.usuario_id and dni != trabajador.usuario.dni:
                raise ValidationError("Esta ficha está vinculada a una cuenta de acceso. El DNI debe coincidir con esa cuenta.")
            if Usuario.objects.filter(dni=dni).exclude(pk=trabajador.usuario_id).exists():
                raise ValidationError("Ese DNI pertenece a otra cuenta registrada. Revise la identidad del trabajador.")
            identidades = list(trabajador.identidades.values_list("pk", flat=True))
            marcas = MarcacionBiometrica.objects.filter(Q(identidad_biometrica_id__in=identidades) | Q(filas_origen__identidad_id__in=identidades)).distinct()
            for marca in marcas:
                comprobar_abierto(timezone.localtime(marca.fecha_hora).date())
            trabajador = formulario.save()
            trabajador.identidades.update(nombre=trabajador.nombre_completo)
            cambios = "; ".join(f"{campo}: {anterior[campo]} → {getattr(trabajador, campo)}" for campo in anterior if anterior[campo] != getattr(trabajador, campo))
            if cambios:
                registrar_historial(None, request.user, "Ficha de trabajador editada", f"Trabajador #{trabajador.pk}. {cambios}")
        return JsonResponse({"trabajador": datos(trabajador)})
    except ValidationError as exc:
        return JsonResponse({"detail": " ".join(exc.messages)}, status=400)
    except IntegrityError:
        return JsonResponse({"detail": "El DNI ya está registrado para otro trabajador."}, status=409)


@login_required
@require_POST
def enviar_a_asistencia(request):
    if not puede_gestionar(request.user):
        return JsonResponse({"detail": "No tiene permiso para enviar marcaciones."}, status=403)
    filtros = {k: request.POST.get(k, "").strip()[:150] for k in ("sede_codigo", "filtro_codigo", "nombre_codigo", "grupo_mes", "grupo_carga")}
    try:
        if request.POST.get("confirmar_identificacion") != "si":
            raise ValidationError("Confirme que revisó las fichas antes de enviarlas.")
        desde, hasta = date.fromisoformat(request.POST.get("desde_envio", "")), date.fromisoformat(request.POST.get("hasta_envio", ""))
        if hasta < desde:
            raise ValidationError("La fecha final no puede ser anterior a la inicial.")
        from asistencia.services.grupos_importacion import validar_grupo_envio
        grupo = validar_grupo_envio(filtros, desde, hasta)
        identidades = IdentidadBiometrica.objects.filter(trabajador__isnull=False)
        if grupo['activo']:
            identidades = identidades.filter(Q(pk__in=grupo['marcas'].values('identidad_biometrica_id')) | Q(pk__in=FilaImportacionBiometrica.objects.filter(marcacion__in=grupo['marcas']).values('identidad_id')))
        if filtros["sede_codigo"]:
            identidades = identidades.filter(sede=filtros["sede_codigo"])
        if filtros["filtro_codigo"]:
            identidades = identidades.filter(codigo__icontains=filtros["filtro_codigo"])
        for termino in filtros["nombre_codigo"].split():
            identidades = identidades.filter(Q(nombre__icontains=termino) | Q(trabajador__nombre_completo__icontains=termino))
        from asistencia.services.transferencia import pasar_a_asistencia
        resultado = pasar_a_asistencia(identidades.values_list("trabajador_id", flat=True).distinct(), desde, hasta, request.user, marcas_ids=grupo['fuente'].values('pk') if grupo['activo'] else None)
        messages.success(request, f"Envío completado: {resultado['nuevas']} jornadas nuevas y {resultado['existentes']} ya existentes. Los eventos disponibles se proponen automáticamente: revíselos y confírmelos antes de aprobar el día.")
        return redirect(reverse("dashboard") + "?" + urlencode({"vista": "asistencia", "desde": resultado["desde"].isoformat(), "hasta": resultado["hasta"].isoformat()}))
    except (ValidationError, ValueError) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Seleccione un periodo de envío válido.")
    return redirect(reverse("dashboard") + "?" + urlencode({"vista": "excel-zk", **filtros}))
