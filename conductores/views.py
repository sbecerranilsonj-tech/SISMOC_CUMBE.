import hashlib
import logging
from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction, DatabaseError
from django.http import FileResponse, HttpResponse, HttpResponseForbidden, JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render as django_render
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.urls import reverse
from .forms import ImportarForm, PeriodoForm, SituacionForm, ConductorForm
from .listados import listado_importaciones
from .models import Auditoria, Conductor, IdentidadConductor, Importacion, Salida, SituacionConductor
from .parser import extraer, identidad
from .services import buscar_conductor, calendario, confirmar, problemas, registrar_situacion, registrar_conductores_reporte, reconocer_registrados, guardar_ficha, editar_situacion_dia, resumen_periodo

logger = logging.getLogger(__name__)


def render(request, plantilla, contexto):
    contexto['puede_gestionar'] = True
    return django_render(request, plantilla, contexto)


def acceso(vista):
    @login_required
    @wraps(vista)
    def protegida(request, *args, **kwargs):
        u = request.user
        if not u.is_active or not u.esta_activo or not (u.is_superuser or u.rol in {'ADMINISTRADOR', 'CONTADORA', 'GERENTE_GENERAL'}):
            return HttpResponseForbidden('No tiene permiso para gestionar conductores.')
        return vista(request, *args, **kwargs)
    return protegida


@acceso
def importar(request):
    form = ImportarForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        etapa = 'lectura'
        archivo = form.cleaned_data['archivo']
        huella = hashlib.sha256(archivo.read()).hexdigest()
        archivo.seek(0)
        existente = Importacion.objects.filter(huella=huella).first()
        if existente:
            messages.info(request, 'Este archivo ya está importado; se abrió su revisión.')
            return redirect(reverse('conductores_importar') + f'?archivo={existente.pk}')
        try:
            filas, incidencias = extraer(archivo)
            etapa = 'almacenamiento'
            archivo.seek(0)
            with transaction.atomic():
                lote = Importacion.objects.create(nombre=archivo.name[:255], huella=huella,
                    inicio=min(f['fecha'] for f in filas), fin=max(f['fecha'] for f in filas),
                    incidencias=incidencias, creado_por=request.user)
                nombres = {f[c] for f in filas for c in ('nombre_uno', 'nombre_dos')}
                vinculados = {nombre: buscar_conductor(nombre) for nombre in nombres}
                objetos = []
                for f in filas:
                    for campo, nombre in [('conductor_uno', 'nombre_uno'), ('conductor_dos', 'nombre_dos')]:
                        f[campo] = vinculados[f[nombre]]
                    objetos.append(Salida(importacion=lote, **f))
                Salida.objects.bulk_create(objetos)
                lote.archivo.save(huella + '.' + archivo.name.rsplit('.', 1)[-1].lower(), archivo)
                Auditoria.objects.create(responsable=request.user, importacion=lote, mensaje=f'Se importaron {len(filas)} registros; quedan pendientes de validar.')
            return redirect(reverse('conductores_importar') + f'?archivo={lote.pk}')
        except ModuleNotFoundError as error:
            form.add_error('archivo', f'Falta el lector {error.name} en el servidor. Instale las dependencias del proyecto y reinicie el servicio.')
        except ValueError as error:
            form.add_error('archivo', str(error))
        except IntegrityError:
            form.add_error('archivo', 'La importación coincide con otro registro. Actualice el historial.')
        except DatabaseError:
            logger.exception('Error de base de datos al importar itinerarios')
            form.add_error('archivo', 'El reporte se leyó, pero no pudo guardarse en la base de datos. Compruebe las migraciones de conductores y la conexión del servidor.')
        except OSError:
            logger.exception('Error de acceso al guardar itinerarios')
            form.add_error('archivo', 'No se pudo acceder al archivo o guardarlo. Revise los permisos de la carpeta privada de itinerarios en el servidor.')
        except Exception as error:
            logger.exception('Error al leer itinerarios')
            form.add_error('archivo', f'Falló la {etapa} del reporte ({type(error).__name__}). No se confirmó ninguna importación. '
                'Envíe este código para revisar la causa; no significa necesariamente que tenga contraseña.')
    return render(request, 'conductores/importar.html', {'seccion': 'importar', 'form': form, **listado_importaciones(request)})


@acceso
@require_GET
def validacion(request):
    destino = reverse('conductores_importar')
    if request.GET:
        destino += '?' + request.GET.urlencode()
    return redirect(destino)


@acceso
def detalle(request, pk):
    lote = get_object_or_404(Importacion, pk=pk)
    if request.method == 'POST':
        try:
            if request.POST.get('accion') == 'reconocer':
                n = reconocer_registrados(lote.pk, request.user)
                messages.success(request, f'Se actualizaron {n} asignaciones. Solo quedan por revisar los nombres sin coincidencia.')
                return redirect('conductores_detalle', pk=pk)
            if request.POST.get('accion') == 'registrar_conductores':
                nuevos, reconocidos = registrar_conductores_reporte(lote.pk, request.user)
                messages.success(request, f'Conductores preparados: {nuevos} nuevos y {reconocidos} reconocidos. Revise las salidas y pulse «Validar y pasar a control».')
                return redirect('conductores_detalle', pk=pk)
            if request.POST.get('accion') == 'confirmar':
                confirmar(lote.pk, request.user)
                messages.success(request, 'Reporte validado. Sus salidas ya están en el control de conductores.')
                return redirect('conductores_control')
            if request.POST.get('accion') == 'vincular':
                with transaction.atomic():
                    lote = Importacion.objects.select_for_update().get(pk=pk)
                    if lote.estado != 'PENDIENTE':
                        raise ValueError('El reporte ya fue validado; sus identidades están bloqueadas.')
                    nombre = request.POST.get('nombre', '')
                    if not lote.salidas.filter(nombre_uno=nombre).exists() and not lote.salidas.filter(nombre_dos=nombre).exists():
                        raise ValueError('El nombre no pertenece a este reporte.')
                    cid = request.POST.get('conductor')
                    if cid:
                        conductor = get_object_or_404(Conductor, pk=cid)
                    else:
                        nuevo = request.POST.get('nuevo_nombre', '').strip()
                        if not nuevo or len(nuevo) > 180:
                            raise ValueError('Indique un nombre válido para el conductor.')
                        conductor = buscar_conductor(nuevo)
                        if not conductor:
                            conductor = Conductor.objects.create(nombre=nuevo)
                    key = identidad(nombre)
                    alias, creado = IdentidadConductor.objects.get_or_create(nombre_origen=key, defaults={'conductor': conductor})
                    if not creado and alias.conductor_id != conductor.pk:
                        raise ValueError('Ese nombre ya está vinculado a otro conductor. Revise la identidad antes de continuar.')
                    lote.salidas.filter(nombre_uno=nombre).update(conductor_uno=conductor)
                    lote.salidas.filter(nombre_dos=nombre).update(conductor_dos=conductor)
                    Auditoria.objects.create(responsable=request.user, importacion=lote, mensaje=f'Se vinculó «{nombre}» con {conductor.nombre}.')
                    messages.success(request, 'Identidad vinculada en todas las salidas de este reporte.')
            return redirect('conductores_detalle', pk=pk)
        except (ValueError, IntegrityError) as error:
            messages.error(request, str(error) if isinstance(error, ValueError) else 'Conflicto de identidad o salida duplicada. Revise los datos antes de confirmar.')
            return redirect('conductores_detalle', pk=pk)
    pendientes = sorted({nombre for s in lote.salidas.filter(anulado=False) for nombre, cid in [(s.nombre_uno, s.conductor_uno_id), (s.nombre_dos, s.conductor_dos_id)] if nombre and not cid})
    errores = problemas(lote, incluir_identidades=False) if lote.estado == 'PENDIENTE' else []
    pagina = Paginator(lote.salidas.select_related('conductor_uno', 'conductor_dos').order_by('fila', 'pk'), 60).get_page(request.GET.get('pagina'))
    return render(request, 'conductores/detalle.html', {'seccion': 'importar', 'lote': lote, 'errores': errores, 'pendientes': pendientes,
        'conductores': Conductor.objects.all(), 'pagina': pagina,
        'cantidad': lote.salidas.count(), 'anulados': lote.salidas.filter(anulado=True).count(), 'historial': lote.historial.select_related('responsable').order_by('-fecha')[:30]})


@acceso
@require_GET
def documento(request, pk):
    lote = get_object_or_404(Importacion, pk=pk)
    return FileResponse(lote.archivo.open('rb'), as_attachment=True, filename=lote.nombre)


@acceso
def control(request):
    ultimo = Importacion.objects.filter(estado='VALIDADO').first()
    hoy = timezone.localdate()
    inicial = {'desde': ultimo.inicio if ultimo else hoy.replace(day=1), 'hasta': ultimo.fin if ultimo else hoy}
    periodo = PeriodoForm(request.GET if ('desde' in request.GET or 'hasta' in request.GET) else inicial)
    dias, filas = [], []
    if periodo.is_valid():
        dias, filas = calendario(periodo.cleaned_data['desde'], periodo.cleaned_data['hasta'], periodo.cleaned_data['q'])
    form = SituacionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            registrar_situacion(usuario=request.user, **form.cleaned_data)
            messages.success(request, 'Situación registrada. El calendario mostrará cualquier cruce con viajes.')
            return redirect(request.get_full_path())
        except ValueError as error:
            form.add_error(None, str(error))
    situaciones = SituacionConductor.objects.filter(activa=True)
    if periodo.is_valid():
        situaciones = situaciones.filter(inicio__lte=periodo.cleaned_data['hasta'], fin__gte=periodo.cleaned_data['desde'])
    pendientes_salida = {s.pk: s for f in filas for c in f['celdas'] for s in c['excluidas'] if s.pendiente_salida}
    salidas_por_confirmar = sorted(pendientes_salida.values(), key=lambda s: (s.fecha, s.hora, s.fila, s.pk))
    filas_resumen = resumen_periodo(filas, periodo.cleaned_data['q']) if periodo.is_valid() else []
    totales = {campo: sum(f[campo] for f in filas_resumen) for campo in ('trayectos', 'trabajados', 'descansos', 'vueltas', 'pago_vueltas', 'horas', 'una_x', 'dos_x', 'pendientes')}
    return render(request, 'conductores/control.html', {'seccion': 'control', 'periodo': periodo, 'form': form,
        'totales': totales, 'filas_resumen': filas_resumen, 'salidas_por_confirmar': salidas_por_confirmar,
        'situacion_tipos': SituacionForm.base_fields['tipo'].choices,
        'dias': dias, 'filas': filas, 'situaciones': situaciones.select_related('conductor').order_by('-inicio')[:100],
        'total_trayectos': sum(f['trayectos'] for f in filas), 'conflictos': sum(f['conflictos'] for f in filas)})


@acceso
@require_POST
def anular_situacion(request, pk):
    with transaction.atomic():
        s = get_object_or_404(SituacionConductor.objects.select_for_update(), pk=pk)
        if s.activa:
            s.activa = False
            s.save(update_fields=['activa'])
            Auditoria.objects.create(responsable=request.user, situacion=s, mensaje=f'Se anuló el registro de {s.get_tipo_display().lower()} de {s.conductor.nombre} ({s.inicio} a {s.fin}).')
    messages.success(request, 'Registro anulado; se conservó en el historial.')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.POST.get('editor_id'):
            request._editor_aviso = 'Registro anulado y calendario actualizado.'
            return ficha(request)
        request._conductores_aviso = 'Registro anulado. El calendario se actualizará al cerrar la ventana.'
        return configuracion(request, completa=True)
    return redirect('conductores_catalogo' if request.POST.get('origen') == 'catalogo' else 'conductores_control')


@acceso
def configuracion(request, completa=False, situacion_form=None):
    form, editando, aviso = ConductorForm(), None, ''
    if request.method == 'POST' and request.POST.get('accion') != 'situacion':
        pk = request.POST.get('id')
        conductor = get_object_or_404(Conductor, pk=pk) if pk else Conductor()
        form = ConductorForm(request.POST, instance=conductor)
        editando = conductor.pk or 'nuevo'
        if form.is_valid():
            try:
                guardar_ficha(form, request.user)
                aviso = 'Datos del conductor guardados.' if completa else 'Datos guardados. El calendario se actualizará al cerrar esta ventana.'
                form, editando = ConductorForm(), None
            except (ValueError, IntegrityError) as error:
                form.add_error(None, str(error) if isinstance(error, ValueError) else 'El nombre ya está registrado.')
    q = request.GET.get('q', '').strip()[:180]
    conductores = sorted(Conductor.objects.select_related('trabajador'), key=lambda c: c.nombre_apellidos)
    if q:
        from .parser import normalizar
        conductores = [c for c in conductores if all(t in normalizar(c.nombre_apellidos) for t in normalizar(q).split())]
    fichas = []
    for c in conductores:
        partes = c.nombre_apellidos.split()
        inicial = {'apellido_paterno': partes[0] if partes else '', 'apellido_materno': partes[1] if len(partes)>2 else '', 'nombres': ' '.join(partes[2:]) if len(partes)>2 else ' '.join(partes[1:])}
        fichas.append({'conductor': c, 'form': form if editando == c.pk else ConductorForm(instance=c, initial=inicial if not c.nombres else None), 'abierto': editando == c.pk})
    contexto = {'fichas': fichas, 'form_nuevo': form if editando == 'nuevo' else ConductorForm(), 'nuevo_abierto': editando == 'nuevo', 'q': q, 'aviso': aviso,
        'completa': completa, 'config_url': reverse('conductores_catalogo' if completa else 'conductores_configuracion'), 'seccion': 'catalogo'}
    if completa:
        popup = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        contexto.update(popup=popup, aviso_situacion=getattr(request, '_conductores_aviso', ''), situacion_form=situacion_form or SituacionForm(), situaciones=SituacionConductor.objects.filter(activa=True).select_related('conductor').order_by('-inicio')[:100])
        if popup:
            return django_render(request, 'conductores/catalogo_contenido.html', contexto)
        return render(request, 'conductores/catalogo.html', contexto)
    return django_render(request, 'conductores/configuracion.html', contexto)


@acceso
def catalogo(request):
    form = None
    if request.method == 'POST' and request.POST.get('accion') == 'situacion':
        form = SituacionForm(request.POST)
        if form.is_valid():
            try:
                registrar_situacion(usuario=request.user, **form.cleaned_data)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    request._conductores_aviso = 'Situación registrada. El calendario se actualizará al cerrar la ventana.'
                    return configuracion(request, completa=True)
                messages.success(request, 'Situación registrada. Ya está reflejada en Control de conductores.')
                return redirect('conductores_catalogo')
            except ValueError as error:
                form.add_error(None, str(error))
    return configuracion(request, completa=True, situacion_form=form)


@acceso
def ficha(request):
    pk = (request.POST.get('id') or request.POST.get('editor_id')) if request.method == 'POST' else request.GET.get('id')
    conductor = get_object_or_404(Conductor, pk=pk) if pk else None
    form = None
    situacion = SituacionForm(initial={'conductor': conductor})
    aviso = getattr(request, '_editor_aviso', '')
    if request.method == 'POST':
        if request.POST.get('accion') == 'situacion':
            if not conductor:
                return HttpResponseForbidden('Registre primero al conductor.')
            datos = request.POST.copy()
            datos['conductor'] = str(conductor.pk)
            situacion = SituacionForm(datos)
            if situacion.is_valid():
                try:
                    registrar_situacion(usuario=request.user, **situacion.cleaned_data)
                    aviso = 'Situación guardada y aplicada al calendario.'
                    situacion = SituacionForm(initial={'conductor': conductor})
                except ValueError as error:
                    situacion.add_error(None, str(error))
        elif request.POST.get('accion') == 'datos':
            form = ConductorForm(request.POST, instance=conductor)
            if form.is_valid():
                try:
                    conductor = guardar_ficha(form, request.user)
                    aviso = 'Datos del conductor guardados.'
                    form = None
                except (ValueError, IntegrityError) as error:
                    form.add_error(None, str(error) if isinstance(error, ValueError) else 'El nombre ya está registrado.')
    if form is None:
        inicial = None
        if conductor and not conductor.nombres:
            partes = conductor.nombre_apellidos.split()
            inicial = {'apellido_paterno': partes[0] if partes else '', 'apellido_materno': partes[1] if len(partes)>2 else '', 'nombres': ' '.join(partes[2:]) if len(partes)>2 else ' '.join(partes[1:])}
        form = ConductorForm(instance=conductor, initial=inicial)
    situaciones = SituacionConductor.objects.filter(conductor=conductor, activa=True).order_by('-inicio') if conductor else []
    return django_render(request, 'conductores/ficha_editor.html', {'conductor': conductor, 'form': form, 'situacion_form': situacion, 'situaciones': situaciones, 'aviso': aviso})


@acceso
@require_POST
def situacion_dia(request):
    form = SituacionForm(request.POST)
    form.fields['motivo'].required = False
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errores': [str(error) for errores in form.errors.values() for error in errores]}, status=400)
    datos = form.cleaned_data
    if datos['inicio'] > datos['fin']:
        return JsonResponse({'ok': False, 'errores': ['La fecha final debe ser igual o posterior a la inicial.']}, status=400)
    candidatas = Salida.objects.filter(importacion__estado='VALIDADO', anulado=False, fecha__range=(datos['inicio'], datos['fin'])).filter(Q(conductor_uno=datos['conductor']) | Q(conductor_dos=datos['conductor']))
    tiene_viajes = any(s.cuenta_para_control for s in candidatas)
    if tiene_viajes:
        return JsonResponse({'ok': False, 'errores': ['El período incluye días con viajes confirmados. Revisa las fechas antes de registrar una situación.']}, status=400)
    try:
        pk = request.POST.get('situacion_id')
        if pk:
            if not pk.isdigit():
                raise ValueError('La situación seleccionada no es válida.')
            editar_situacion_dia(int(pk), datos['conductor'], datos['inicio'], datos['tipo'], request.user, fin=datos['fin'])
        else:
            registrar_situacion(usuario=request.user, **datos)
    except ValueError as error:
        return JsonResponse({'ok': False, 'errores': [str(error)]}, status=400)
    return JsonResponse({'ok': True})


@acceso
@require_GET
def exportar_calendario(request):
    from .exportacion import libro_calendario
    periodo = PeriodoForm(request.GET)
    if not periodo.is_valid():
        return HttpResponse('Revise las fechas del período para exportar el calendario.', status=400)
    datos = periodo.cleaned_data
    dias, filas = calendario(datos['desde'], datos['hasta'], datos['q'])
    response = HttpResponse(libro_calendario(datos['desde'], datos['hasta'], dias, filas, resumen_periodo(filas, datos['q'])), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="calendario_conductores_{datos["desde"]}_{datos["hasta"]}.xlsx"'
    return response


@acceso
@require_POST
def resolver_salida(request, pk):
    decision = request.POST.get('decision')
    if decision not in ('REALIZADO', 'CANCELADO'):
        return JsonResponse({'ok': False, 'errores': ['Seleccione si la salida se realizó o fue cancelada.']}, status=400)
    with transaction.atomic():
        salida = get_object_or_404(Salida.objects.select_for_update(), pk=pk, importacion__estado='VALIDADO')
        if salida.anulado:
            return JsonResponse({'ok': False, 'errores': ['El reporte original indica que esta salida está anulada.']}, status=400)
        if decision == 'REALIZADO' and SituacionConductor.objects.filter(conductor_id__in=[salida.conductor_uno_id, salida.conductor_dos_id], activa=True, inicio__lte=salida.fecha, fin__gte=salida.fecha).exists():
            return JsonResponse({'ok': False, 'errores': ['Hay una situación registrada para un conductor en esta fecha. Revisa su configuración antes de confirmar la salida.']}, status=400)
        if salida.estado_operativo != decision:
            anterior = salida.estado_control
            salida.estado_operativo = decision
            salida.save(update_fields=['estado_operativo'])
            Auditoria.objects.create(responsable=request.user, importacion=salida.importacion, mensaje=f'Fila {salida.fila}, {salida.fecha} {salida.hora}: {anterior} → {salida.estado_control}. Confirmación operativa; se conserva el reporte original.')
    return JsonResponse({'ok': True})
