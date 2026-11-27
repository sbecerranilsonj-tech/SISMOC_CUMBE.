"""La app consulta el mismo resumen operativo que el calendario web.

No valida ni modifica días: la validación y las cancelaciones corresponden a
Control de conductores. Se conserva el contrato de la API para otros roles.
"""
import calendar
import json
from datetime import date

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from conductores.services import calendario
from . import views
from .models import Perfil, Sesion


def resumen_web(conductor_id, desde, hasta):
    _, filas = calendario(desde, hasta)
    fila = next((f for f in filas if f['conductor'].pk == conductor_id), None)
    if not fila:
        return {'trayectos_realizados': 0, 'vueltas': 0.0, 'estimado': 0,
                'HORA': 0, 'X': 0, 'XX': 0}
    return {
        'trayectos_realizados': fila['trayectos'],
        'vueltas': float(fila['vueltas']),
        'estimado': int(fila['pago_vueltas']),
        'HORA': fila['horas'],
        'X': fila['una_x'],
        'XX': fila['dos_x'],
    }


@csrf_exempt
def api_con_resumen_web(request, accion):
    respuesta = views.api(request, accion)
    if accion not in ('inicio', 'login', 'activar', 'rutas_periodo') or respuesta.status_code != 200:
        return respuesta
    datos = json.loads(respuesta.content)
    if not datos.get('ok') or 'resumen' not in datos:
        return respuesta
    if accion == 'rutas_periodo':
        token = request.headers.get('Authorization', '').removeprefix('Bearer ')
        sesion = Sesion.objects.filter(
            token_hash=views.hash_token(token), activa=True, vence__gt=timezone.now()
        ).select_related('perfil').first()
        perfil = sesion.perfil if sesion else None
        mes = date.fromisoformat(datos['mes'] + '-01')
        desde = mes
        hasta = date(mes.year, mes.month, calendar.monthrange(mes.year, mes.month)[1])
    else:
        perfil = Perfil.objects.filter(pk=datos.get('perfil', {}).get('id')).first()
        hoy = timezone.now().astimezone(views.PERU).date()
        desde, hasta = hoy.replace(day=1), hoy
    if perfil and perfil.conductor_id:
        datos['resumen'].update(resumen_web(perfil.conductor_id, desde, hasta))
        return JsonResponse(datos, json_dumps_params={'ensure_ascii': False})
    return respuesta
