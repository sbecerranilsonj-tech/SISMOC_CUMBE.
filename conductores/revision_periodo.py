"""Revisión global del período; nunca modifica salidas durante la consulta."""
from django.core import signing
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .forms import PeriodoForm
from .models import Auditoria, Salida, SituacionConductor
from .services import calendario
from .views import acceso

SALT = 'conductores.revision-periodo.v1'


def estado_periodo(desde, hasta):
    # Sin filtro de búsqueda: todos los conductores con actividad en este período.
    _, filas = calendario(desde, hasta)
    faltantes = [
        {'conductor': f['conductor'].nombre_apellidos, 'fecha': str(c['fecha'])}
        for f in filas for c in f['celdas']
        if c['etiqueta'] in ('—', 'PR') or c['conflicto']
    ]
    # Una salida pertenece a dos conductores: deduplicar por id.
    pendientes = sorted({
        s.pk for f in filas for c in f['celdas']
        for s in c['excluidas'] if s.pendiente_salida
    })
    return faltantes, pendientes, len(filas)


@acceso
@require_http_methods(['GET', 'POST'])
def revision_periodo(request):
    form = PeriodoForm(request.GET if request.method == 'GET' else request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': 'Seleccione un período válido de 1 a 62 días.'}, status=400)
    desde, hasta = form.cleaned_data['desde'], form.cleaned_data['hasta']

    if request.method == 'GET':
        faltantes, pendientes, conductores = estado_periodo(desde, hasta)
        comprobante = signing.dumps(
            {'desde': str(desde), 'hasta': str(hasta), 'pendientes': pendientes},
            salt=SALT,
        ) if not faltantes and pendientes else ''
        return JsonResponse({'ok': True, 'faltantes': faltantes,
                             'pendientes': len(pendientes), 'conductores': conductores,
                             'comprobante': comprobante})

    try:
        comprobante = signing.loads(request.POST.get('comprobante', ''), salt=SALT, max_age=600)
    except signing.BadSignature:
        return JsonResponse({'ok': False, 'error': 'La revisión caducó; vuelve a revisar el período.'}, status=409)
    if comprobante['desde'] != str(desde) or comprobante['hasta'] != str(hasta):
        return JsonResponse({'ok': False, 'error': 'El período cambió; vuelve a revisarlo.'}, status=409)

    with transaction.atomic():
        # Bloquear las salidas y situaciones del período antes de volver a revisar.
        list(Salida.objects.select_for_update().filter(
            importacion__estado='VALIDADO', fecha__range=(desde, hasta)
        ).order_by('pk').values_list('pk', flat=True))
        list(SituacionConductor.objects.select_for_update().filter(
            activa=True, inicio__lte=hasta, fin__gte=desde
        ).order_by('pk').values_list('pk', flat=True))
        faltantes, pendientes, _ = estado_periodo(desde, hasta)
        if faltantes or pendientes != comprobante['pendientes']:
            return JsonResponse({'ok': False, 'error': 'El calendario cambió; vuelve a revisarlo.'}, status=409)
        salidas = Salida.objects.filter(pk__in=pendientes, estado_operativo='AUTO', anulado=False)
        if salidas.count() != len(pendientes):
            return JsonResponse({'ok': False, 'error': 'Una salida cambió; vuelve a revisarlo.'}, status=409)
        revisadas = list(salidas.select_related('importacion').order_by('pk'))
        if any(not s.pendiente_salida or s.importacion.estado != 'VALIDADO' for s in revisadas):
            return JsonResponse({'ok': False, 'error': 'Una salida cambió; vuelve a revisarlo.'}, status=409)
        for salida in revisadas:
            salida.estado_operativo = 'CANCELADO'
            salida.save(update_fields=['estado_operativo'])
            Auditoria.objects.create(
                responsable=request.user, importacion=salida.importacion,
                mensaje=f'Fila {salida.fila}, {salida.fecha} {salida.hora}: Sin ventas → Cancelado. Revisión global {desde} a {hasta}; reporte original conservado.',
            )
    return JsonResponse({'ok': True, 'canceladas': len(pendientes)})
