import hashlib
import logging
from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Sum, Count
from django.http import FileResponse, HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_GET
from .forms import ImportarForm, MovimientoForm
from .models import EstadoCuenta, Movimiento, Revision
from .parser import extraer
from .listados import contexto_importador

logger = logging.getLogger(__name__)


def acceso(vista):
    @login_required
    @wraps(vista)
    def protegida(request, *args, **kwargs):
        u = request.user
        if not u.is_active or not u.esta_activo or not (u.is_superuser or u.rol in {'ADMINISTRADOR', 'CONTADORA', 'GERENTE_GENERAL'}):
            return HttpResponseForbidden('No tiene permiso para consultar información bancaria.')
        return vista(request, *args, **kwargs)
    return protegida


@acceso
def panel(request):
    form = ImportarForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        archivo = form.cleaned_data['pdf']
        huella = hashlib.sha256(archivo.read()).hexdigest()
        archivo.seek(0)
        existente = EstadoCuenta.objects.filter(huella=huella).first()
        if existente:
            messages.info(request, 'Este PDF ya fue importado. Se abrió su registro existente.')
            return redirect('bancos_detalle', pk=existente.pk)
        try:
            datos, filas = extraer(archivo)
            archivo.seek(0)
            with transaction.atomic():
                # Evita dos documentos diferentes para un período ya registrado.
                if EstadoCuenta.objects.filter(cuenta=datos['cuenta'], inicio__lte=datos['fin'], fin__gte=datos['inicio']).exists():
                    raise ValueError('Ya existe un estado de esa cuenta con fechas superpuestas. Revise el historial antes de importar otro.')
                estado = EstadoCuenta.objects.create(**datos, huella=huella, creado_por=request.user)
                Movimiento.objects.bulk_create([Movimiento(estado_cuenta=estado, **fila) for fila in filas])
                estado.pdf.save(f'{huella}.pdf', archivo, save=True)
                Revision.objects.create(estado_cuenta=estado, responsable=request.user, detalle={'accion': 'Importación', 'movimientos': len(filas)})
            messages.success(request, 'PDF importado. Revise los movimientos antes de pasarlos al control bancario.')
            return redirect('bancos_detalle', pk=estado.pk)
        except ValueError as error:
            form.add_error('pdf', str(error))
        except IntegrityError:
            form.add_error('pdf', 'El documento ya está registrado. Actualice el historial.')
        except ModuleNotFoundError as error:
            logger.exception('Dependencia no instalada en el servidor bancario')
            if error.name == 'pdfplumber':
                form.add_error('pdf', 'El lector PDF no está instalado en el servidor. El administrador debe instalar pdfplumber en el servicio web y reiniciarlo. El archivo no fue importado.')
            else:
                form.add_error('pdf', 'Falta una dependencia del lector PDF en el servidor. El administrador debe reinstalar requirements.txt en el servicio web. El archivo no fue importado.')
        except Exception:
            logger.exception('Error al importar estado de cuenta BCP')
            form.add_error('pdf', 'No se pudo procesar el PDF. Verifique que sea legible y que las dependencias del módulo estén instaladas.')
    contexto = contexto_importador(request)
    if contexto['estado']:
        return detalle(request, contexto['estado'].pk, contexto=contexto, form_importacion=form, procesar_post=False)
    return render(request, 'bancos/panel.html', {'seccion': 'importar', 'form': form, **contexto})


@acceso
@require_GET
def validacion(request):
    consulta = request.GET.copy()
    consulta.setdefault('situacion', 'PENDIENTE')
    return redirect(reverse('bancos_importar') + '?' + consulta.urlencode())


@acceso
def detalle(request, pk, contexto=None, form_importacion=None, procesar_post=True):
    estado = get_object_or_404(EstadoCuenta, pk=pk)
    form_edicion = None
    if request.method == 'POST' and procesar_post:
        with transaction.atomic():
            estado = EstadoCuenta.objects.select_for_update().get(pk=pk)
            if estado.estado == 'VALIDADO':
                messages.error(request, 'El período ya fue validado y no admite cambios.')
                return redirect('bancos_detalle', pk=pk)
            if request.POST.get('accion') == 'recomprobar':
                try:
                    with estado.pdf.open('rb') as archivo:
                        datos, originales = extraer(archivo)
                    guardados = estado.movimientos.aggregate(cargo=Sum('cargo'), abono=Sum('abono'))
                    coinciden = all(datos[k] == getattr(estado, k) for k in ('cuenta', 'inicio', 'fin', 'saldo_inicial', 'saldo_final'))
                    coinciden = coinciden and len(originales) == estado.movimientos.count()
                    coinciden = coinciden and all(sum(m[k] for m in originales) == guardados[k] for k in ('cargo', 'abono'))
                    if not coinciden:
                        messages.error(request, 'La lectura actual del PDF difiere de los datos guardados. Se conservaron los movimientos y sus observaciones; revise las diferencias antes de validar.')
                    else:
                        estado.incidencias = datos['incidencias']
                        estado.save(update_fields=['incidencias'])
                        Revision.objects.create(estado_cuenta=estado, responsable=request.user, detalle={'accion': 'Comprobación del PDF', 'incidencias': len(estado.incidencias)})
                        messages.success(request, 'Comprobación terminada. Los movimientos y sus correcciones se conservaron.')
                except Exception:
                    logger.exception('No se pudo recomprobar el estado bancario')
                    messages.error(request, 'No se pudo volver a comprobar el PDF. Se conservaron los datos existentes.')
            elif request.POST.get('accion') == 'validar':
                if estado.incidencias or estado.diferencia != 0:
                    messages.error(request, 'No se puede validar: existen líneas sin interpretar o diferencias de saldo.')
                elif EstadoCuenta.objects.filter(cuenta=estado.cuenta, inicio__lte=estado.fin, fin__gte=estado.inicio, estado='VALIDADO').exclude(pk=pk).exists():
                    messages.error(request, 'Ya hay un período validado que se superpone con este.')
                else:
                    estado.estado, estado.validado_por, estado.validado = 'VALIDADO', request.user, timezone.now()
                    estado.save(update_fields=['estado', 'validado_por', 'validado'])
                    Revision.objects.create(estado_cuenta=estado, responsable=request.user, detalle={'accion': 'Validación y pase a control'})
                    messages.success(request, 'Movimientos validados e incorporados al control bancario.')
                    return redirect('bancos_control')
            elif request.POST.get('accion') == 'editar':
                movimiento = get_object_or_404(Movimiento, pk=request.POST.get('movimiento', '0') if request.POST.get('movimiento', '').isdigit() else 0, estado_cuenta=estado)
                antes = {k: str(getattr(movimiento, k)) for k in MovimientoForm.Meta.fields}
                form_edicion = MovimientoForm(request.POST, instance=movimiento)
                if form_edicion.is_valid():
                    if not form_edicion.cleaned_data.get('observacion', '').strip():
                        form_edicion.add_error('observacion', 'Explique el motivo de la corrección.')
                    else:
                        movimiento = form_edicion.save()
                        Revision.objects.create(estado_cuenta=estado, movimiento=movimiento, responsable=request.user, detalle={'accion': 'Corrección', 'antes': antes, 'despues': {k: str(getattr(movimiento, k)) for k in MovimientoForm.Meta.fields}})
                        messages.success(request, 'Corrección guardada con su historial.')
                        return redirect('bancos_detalle', pk=pk)
        if form_edicion is None:
            return redirect('bancos_detalle', pk=pk)
    if request.GET.get('editar', '').isdigit() and estado.estado == 'PENDIENTE':
        form_edicion = MovimientoForm(instance=get_object_or_404(Movimiento, pk=request.GET['editar'], estado_cuenta=estado))
    filas = estado.movimientos.all().order_by('orden')
    saldo = estado.saldo_inicial
    for m in filas:
        saldo += m.abono - m.cargo
        m.saldo = saldo
    filas = list(filas)
    q = request.GET.get('q', '')[:200].strip()
    if q:
        filas = [m for m in filas if q.casefold() in m.descripcion.casefold()]
    pagina = Paginator(filas, 100).get_page(request.GET.get('page'))
    totales = estado.movimientos.aggregate(cargos=Sum('cargo'), abonos=Sum('abono'))
    contexto = contexto if contexto is not None else contexto_importador(request, seleccionado=estado)
    return render(request, 'bancos/panel.html', {**contexto, 'seccion': 'importar', 'form': form_importacion if form_importacion is not None else ImportarForm(), 'estado': estado, 'pagina': pagina, 'totales': totales, 'form_edicion': form_edicion, 'historial': estado.revisiones.select_related('responsable').order_by('-fecha')[:30]})


@acceso
def control(request):
    estados = EstadoCuenta.objects.filter(estado='VALIDADO')
    filas = Movimiento.objects.filter(estado_cuenta__estado='VALIDADO').select_related('estado_cuenta')
    seleccion = request.GET.get('estado', '')
    if seleccion.isdigit():
        filas = filas.filter(estado_cuenta_id=int(seleccion))
    if request.GET.get('q'):
        filas = filas.filter(descripcion__icontains=request.GET['q'][:200])
    fecha = request.GET.get('fecha', '')
    if fecha:
        from datetime import date
        try:
            filas = filas.filter(fecha=date.fromisoformat(fecha))
        except ValueError:
            messages.error(request, 'La fecha indicada no es válida.')
    tipo = request.GET.get('tipo')
    if tipo in {'cargo', 'abono'}:
        filas = filas.filter(**{f'{tipo}__gt': 0})
    totales = filas.aggregate(cargos=Sum('cargo'), abonos=Sum('abono'))
    diarios = filas.values('fecha').annotate(cargos=Sum('cargo'), abonos=Sum('abono')).order_by('-fecha')
    consulta = request.GET.copy()
    consulta.pop('page', None)
    return render(request, 'bancos/control.html', {'seccion': 'control', 'estados': estados, 'pagina': Paginator(filas.order_by('-fecha', 'estado_cuenta_id', 'orden'), 100).get_page(request.GET.get('page')), 'totales': totales, 'diarios': diarios, 'consulta': consulta.urlencode(), 'seleccion': seleccion})


@acceso
def documento(request, pk):
    estado = get_object_or_404(EstadoCuenta, pk=pk)
    return FileResponse(estado.pdf.open('rb'), content_type='application/pdf', as_attachment=False, filename='estado-bcp.pdf')


@acceso
def diagnostico(request, pk):
    estado = get_object_or_404(EstadoCuenta, pk=pk)
    totales = estado.movimientos.aggregate(cargo=Sum('cargo'), abono=Sum('abono'), cantidad=Count('pk'))
    diferencia = estado.saldo_inicial + (totales['abono'] or 0) - (totales['cargo'] or 0) - estado.saldo_final
    lineas = ['DIAGNÓSTICO BANCARIO SISMOC', 'Versión: 20261106-diagnostico-rapido', f'Estado interno: {estado.pk}', f'Fecha: {timezone.localtime():%d/%m/%Y %H:%M}', f'Cuenta: terminación {estado.cuenta[-4:]}', f'Período: {estado.inicio:%d/%m/%Y} al {estado.fin:%d/%m/%Y}', f'Estado: {estado.get_estado_display()}', f'Movimientos: {totales["cantidad"]}', f'Saldo inicial guardado: {estado.saldo_inicial:,.2f}', f'Saldo final guardado: {estado.saldo_final:,.2f}', f'Cargos guardados: {totales["cargo"] or 0:,.2f}', f'Abonos guardados: {totales["abono"] or 0:,.2f}', f'Diferencia de saldo: {diferencia:,.2f}', '', 'MOTIVOS DEL BLOQUEO']
    # Las líneas de movimientos pueden contener nombres; no se exportan al diagnóstico.
    for i in estado.incidencias:
        lineas.append(i if not i.startswith('Página ') else 'Existe una línea de movimiento sin interpretar; consultar la incidencia en pantalla.')
    if not estado.incidencias:
        lineas.append('Sin incidencias de lectura guardadas.')
    lineas += ['', 'ALCANCE', 'Este diagnóstico usa los datos y las incidencias guardadas. No vuelve a procesar el PDF.', 'Para actualizar las comprobaciones, utilice Volver a comprobar PDF.']
    revision = estado.revisiones.select_related('responsable').order_by('-fecha').first()
    if revision:
        lineas += ['', 'ÚLTIMA ACCIÓN', str(revision.detalle.get('accion', 'Revisión')), f'Fecha: {timezone.localtime(revision.fecha):%d/%m/%Y %H:%M}']
    respuesta = HttpResponse('\n'.join(lineas), content_type='text/plain; charset=utf-8')
    respuesta['Content-Disposition'] = f'attachment; filename="diagnostico-bcp-{estado.pk}.txt"'
    respuesta['Cache-Control'] = 'no-store'
    return respuesta
