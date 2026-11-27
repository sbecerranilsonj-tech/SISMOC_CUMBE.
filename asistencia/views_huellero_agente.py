"""Puente entre los agentes locales (uno por sede) y la nube.

La identificación de la persona se hace por **nombre**, no por el ID del
dispositivo: ese ID se repite entre sedes. Si el nombre no es único, la marca
queda «Por identificar» en vez de asignarse a alguien equivocado.
"""
import hashlib
import json
from datetime import datetime
from unicodedata import normalize as normalizar_unicode
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.models import Usuario
from asistencia.models import MarcacionBiometrica
from asistencia.services.revision import puede_gestionar
from asistencia.services.zkteco_live import (
    agente_por_id, agentes_configurados, clasificar_ventana, configuracion_agente,
    estados_por_agente, guardar_estado_agente, obtener_estado_agente,
    ordenar_prueba_conexion, tomar_comando, clave_comando,
)
from django.core.cache import cache

PERU = ZoneInfo("America/Lima")


def _token_valido(request):
    configurado = getattr(settings, "HUELLERO_AGENT_TOKEN", "")
    if not configurado:
        return False
    cabecera = request.headers.get("Authorization", "")
    if cabecera.startswith("Bearer "):
        return cabecera[7:].strip() == configurado
    try:
        return json.loads(request.body or b"{}").get("token") == configurado
    except (ValueError, AttributeError):
        return False


def _sin_token():
    return JsonResponse(
        {"detail": "El agente no está autorizado o el servidor no tiene HUELLERO_AGENT_TOKEN."},
        status=403,
    )


def _agente_id(request, datos=None):
    valor = (request.headers.get("X-Agente-Id")
             or request.GET.get("agente_id")
             or (datos or {}).get("agente_id")
             or "PRINCIPAL")
    return str(valor)


def _normalizar(texto):
    return ' '.join(
        normalizar_unicode('NFD', str(texto or '')).encode('ascii', 'ignore')
        .decode().upper().split()
    )


def _usuario(marca, sede=None):
    nombre = _normalizar(marca.get("nombre") or marca.get("nombre_empleado"))
    if nombre:
        candidatos = []
        tokens = set(nombre.split())
        for usuario in Usuario.objects.filter(esta_activo=True).select_related("ficha_trabajador"):
            completo = _normalizar(usuario.nombre_completo)
            corto = _normalizar(usuario.nombre_corto)
            if completo == nombre or corto == nombre:
                candidatos.append(usuario)
            elif len(tokens) >= 2 and (tokens <= set(completo.split())
                                       or tokens <= set(corto.split())):
                candidatos.append(usuario)
        if sede:
            en_sede = [u for u in candidatos
                       if _normalizar(u.agencia_sede) == _normalizar(sede)]
            if en_sede:
                return en_sede[0], ''
        if len(candidatos) == 1:
            return candidatos[0], ''
        if len(candidatos) > 1:
            return None, f'Nombre repetido: {nombre[:40]}'
        return None, f'Por identificar: {nombre[:40]}'
    # Sin nombre, solo se usa el ID si es único en todo el sistema.
    uid = str(marca.get("user_id") or "").strip()
    if uid.isdigit():
        encontrados = list(Usuario.objects.filter(zkteco_user_id=int(uid))[:2])
        if len(encontrados) == 1:
            return encontrados[0], ''
    return None, 'Sin nombre enviado por el agente'


@csrf_exempt
@require_GET
def agente_comando(request):
    """Cada agente consulta solo las órdenes dirigidas a su agente_id."""
    if not _token_valido(request):
        return _sin_token()
    agente_id = _agente_id(request)
    return JsonResponse({"comando": tomar_comando(agente_id), "agente_id": agente_id})


def _momento(valor):
    texto = str(valor or "").strip().replace("Z", "+00:00")
    try:
        resultado = datetime.fromisoformat(texto)
    except ValueError as exc:
        raise ValueError(f"Fecha de marcación inválida: {valor}") from exc
    if timezone.is_naive(resultado):
        resultado = timezone.make_aware(resultado, PERU)
    return resultado


@csrf_exempt
@require_POST
@transaction.atomic
def agente_reportar(request):
    """Recibe estado y marcas; guarda sede y resuelve persona por nombre."""
    if not _token_valido(request):
        return _sin_token()
    try:
        datos = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"detail": "Cuerpo JSON inválido."}, status=400)

    agente_id = _agente_id(request, datos)
    agente = agente_por_id(agente_id)
    sede = str(datos.get("sede") or agente["sede"])
    serie = str(datos.get("serie") or agente["serie"]
                or (datos.get("estado") or {}).get("numero_serie") or "")
    ip = str(datos.get("ip") or agente["ip"])
    estado = datos.get("estado") or {}
    estado.update({"agente_id": agente_id, "sede": sede, "ip": ip})
    guardar_estado_agente(estado, agente_id)

    creadas = 0
    duplicadas = 0
    errores = []
    tipos = set(MarcacionBiometrica.TipoEvento.values)

    for marca in datos.get("marcas") or []:
        uid = str(marca.get("uid") or "").strip()
        if not uid:
            errores.append("Marcación sin UID; se omitió.")
            continue
        huella = hashlib.sha256(f"{serie}:{uid}".encode()).hexdigest()[:64]
        if MarcacionBiometrica.objects.filter(huella_importacion=huella).exists():
            duplicadas += 1
            continue
        try:
            momento = _momento(marca.get("fecha_hora"))
            usuario, aviso = _usuario(marca, sede)
            tipo = marca.get("tipo_evento") or MarcacionBiometrica.TipoEvento.SIN_CLASIFICAR
            tipo = tipo if tipo in tipos else MarcacionBiometrica.TipoEvento.SIN_CLASIFICAR
            observacion = aviso or clasificar_ventana(momento)
            MarcacionBiometrica.objects.create(
                usuario=usuario,
                dni=str(marca.get("dni") or (usuario.dni if usuario else ""))[:8],
                nombre_empleado=str(marca.get("nombre") or (
                    usuario.nombre_completo if usuario else ""))[:150],
                zkteco_user_id=int(marca["user_id"]) if str(marca.get("user_id") or "").isdigit() else None,
                fecha_hora=momento,
                tipo_evento=tipo,
                origen=MarcacionBiometrica.OrigenMarcacion.ZKTECO_EN_LINEA,
                dispositivo_ip=ip,
                sede=sede[:120],
                es_valida=True,
                estado_reportado=observacion[:60],
                huella_importacion=huella,
            )
            creadas += 1
        except (ValueError, ValidationError) as exc:
            errores.append(str(exc))

    return JsonResponse({"creadas": creadas, "duplicadas": duplicadas,
                         "errores": errores[:20], "recibidas": len(datos.get("marcas") or []),
                         "agente_id": agente_id, "sede": sede})


@login_required
@require_POST
def agente_prueba_web(request):
    """Desde el popup: prueba dirigida a un agente/sede concreto."""
    if not puede_gestionar(request.user):
        return HttpResponseForbidden("No tiene permiso para comprobar el huellero.")
    agente_id = request.POST.get("agente_id") or agentes_configurados()[0]["id"]
    comando = ordenar_prueba_conexion(agente_id)
    return JsonResponse({"comando": comando, "mensaje": "Solicitud enviada al agente de la sede."})


@login_required
@require_GET
def agente_estado_web(request):
    """Estado de cada agente y si sigue pendiente una prueba."""
    if not puede_gestionar(request.user):
        return HttpResponseForbidden("No tiene permiso para consultar el huellero.")
    estados = estados_por_agente()
    pendientes = {a["id"]: bool(cache.get(clave_comando(a["id"])))
                  for a in agentes_configurados()}
    return JsonResponse({
        "estados": estados,
        "config": configuracion_agente(),
        "comandos_pendientes": pendientes,
        "estado": obtener_estado_agente(),
    })
