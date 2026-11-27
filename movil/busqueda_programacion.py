"""Referencias del formulario de programación, siempre desde la base de datos."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from conductores.models import Conductor
from conductores.parser import normalizar
from .models import Perfil
from .programacion_manual import placas_disponibles, sedes_disponibles
from .views import VENTAS


def busqueda_por_letra(valores, consulta, tokens, origen='base', extra=None):
    resultados = []
    for valor in valores:
        campo = dict(valor, **(extra or {}))
        texto = normalizar(' '.join(str(v or '') for v in (
            campo.get('nombre'), campo.get('sede'), campo.get('detalle'),
            campo.get('id') or '',
        )))
        if origen == 'sede':
            texto = normalizar(' '.join(str(v or '') for v in (
                valor, campo.get('detalle', ''),
            )))
        if all(t in texto for t in tokens) or (
                not tokens and consulta and consulta in normalizar(valor)):
            resultados.append(campo)
    resultados.sort(key=lambda o: (
        not normalizar(o.get('nombre') or o.get('id', '')).startswith(consulta),
        normalizar(o.get('nombre') or o.get('id', '')), str(o.get('id', ''))))
    return resultados[:8]


@login_required
@require_GET
@never_cache
def sugerencias_programacion(request):
    if request.user.rol not in VENTAS or request.user.rol == 'CONTADORA':
        return HttpResponseForbidden('Esta sección corresponde a Boletería.')
    tipo = request.GET.get('tipo', '')
    if tipo not in ('sede', 'placa', 'conductor', 'embarcador'):
        return JsonResponse({'resultados': []}, status=400)
    consulta = normalizar(request.GET.get('q', '')[:100])
    if not consulta:
        return JsonResponse({'resultados': []})
    tokens = consulta.split()
    if tipo == 'embarcador':
        valores = (
            {'id': str(p.pk),
             'nombre': (p.trabajador.nombre_completo if p.trabajador_id
                        else (p.usuario.get_full_name() or p.codigo)),
             'detalle': 'Encargado de embarque activo'}
            for p in Perfil.objects.filter(
                activo=True, usuario__rol='OPERADOR_EMBARQUE',
                usuario__is_active=True, usuario__esta_activo=True,
            ).select_related('usuario', 'trabajador')
        )
    elif tipo == 'conductor':
        activos = set(Perfil.objects.filter(
            conductor__isnull=False, activo=True,
            usuario__is_active=True, usuario__esta_activo=True,
        ).values_list('conductor_id', flat=True))
        valores = (
            {'id': str(c.pk), 'nombre': c.nombre_apellidos,
             'detalle': 'Cuenta móvil activa' if c.pk in activos
             else 'Sin cuenta móvil activa · pendiente de revisión'}
            for c in Conductor.objects.select_related('trabajador')
        )
    else:
        valores = sedes_disponibles() if tipo == 'sede' else placas_disponibles()
        valores = ({'id': v, 'nombre': v,
                    'detalle': 'Sede registrada' if tipo == 'sede'
                    else 'Placa de itinerario validado'} for v in valores)
    resultados = busqueda_por_letra(list(valores), consulta, tokens, tipo)
    return JsonResponse({'resultados': resultados})
