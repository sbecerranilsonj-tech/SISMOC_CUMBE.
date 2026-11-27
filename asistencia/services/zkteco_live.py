"""Estado del huellero, agentes por sede y registros persistidos.

Cada sede ejecuta su propio agente con un agente_id. La nube no abre la IP
privada del equipo: solo recibe lo que cada agente reporta por HTTPS.
"""
import socket
import uuid
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from asistencia.models import MarcacionBiometrica


def _token():
    return settings.HUELLERO_AGENT_TOKEN


def _config_base():
    return getattr(settings, "ZKTECO_CONFIG", {})


def agentes_configurados():
    cfg = getattr(settings, "HUELLERO_AGENTES", {}) or {}
    if not isinstance(cfg, dict) or not cfg:
        base = _config_base()
        cfg = {"PRINCIPAL": {
            "sede": "Sede principal", "ip": base.get("IP", "192.168.10.202"),
            "puerto": base.get("PORT", 4370), "serie": base.get("SERIE", ""),
        }}
    base = _config_base()
    return [
        {"id": str(clave), "sede": str(valor.get("sede") or clave),
         "ip": str(valor.get("ip") or base.get("IP", "192.168.10.202")),
         "puerto": int(valor.get("puerto") or base.get("PORT", 4370)),
         "serie": str(valor.get("serie") or base.get("SERIE", ""))}
        for clave, valor in cfg.items()
    ]


def agente_por_id(agente_id):
    agentes = agentes_configurados()
    return next((a for a in agentes if a["id"] == str(agente_id)), agentes[0])


def configuracion_agente():
    return {
        "agentes": agentes_configurados(),
        "token": _token(),
        "intervalo": getattr(settings, "HUELLERO_AGENT_INTERVALO", 30),
        "ventanas": getattr(settings, "HUELLERO_REFRIGERIO", {}),
    }


def clave_estado(agente_id):
    return f"huellero_estado:{agente_id}"


def clave_comando(agente_id):
    return f"huellero_comando:{agente_id}"


def estados_por_agente():
    return {a["id"]: cache.get(clave_estado(a["id"]), {})
            for a in agentes_configurados()}


def obtener_estado_agente(agente_id=None):
    if agente_id:
        return cache.get(clave_estado(agente_id), {})
    return next((e for e in estados_por_agente().values() if e.get("fecha")), {})


def guardar_estado_agente(datos, agente_id=None):
    agente_id = str(agente_id or datos.get("agente_id") or "PRINCIPAL")
    estado = {**datos, "agente_id": agente_id}
    cache.set(clave_estado(agente_id), estado, timeout=3600)
    return estado


def ordenar_prueba_conexion(agente_id):
    agente_id = str(agente_id or agentes_configurados()[0]["id"])
    comando = {"id": str(uuid.uuid4()), "tipo": "PROBAR", "agente_id": agente_id,
               "creado": timezone.localtime().strftime("%d/%m/%Y %H:%M:%S")}
    cache.set(clave_comando(agente_id), comando, timeout=300)
    return comando


def tomar_comando(agente_id):
    agente_id = str(agente_id or "PRINCIPAL")
    comando = cache.get(clave_comando(agente_id))
    if comando:
        cache.delete(clave_comando(agente_id))
    return comando or {}


def clasificar_ventana(momento):
    """Etiqueta informativa: nunca descuenta ni modifica la marcación."""
    hora = timezone.localtime(momento).strftime("%H:%M")
    for nombre, (inicio, fin) in getattr(settings, "HUELLERO_REFRIGERIO", {}).items():
        if inicio <= hora <= fin:
            return f"Refrigerio {nombre}"
    return "Fuera de ventana de refrigerio"


class ZKTecoLiveClient:
    def __init__(self, ip: Optional[str] = None, port: Optional[int] = None, timeout: int = 4):
        cfg = _config_base()
        self.ip = ip or cfg.get("IP", "192.168.10.202")
        self.port = port or cfg.get("PORT", 4370)
        self.timeout = timeout

    def probar_conexion(self):
        """Comprueba la red. La descarga real la hace el agente en la sede."""
        resultado = {"ip": self.ip, "puerto": self.port, "conectado": False, "modo": "AGENTE_LOCAL"}
        estado = obtener_estado_agente()
        if estado:
            resultado.update({
                "conectado": bool(estado.get("conectado")),
                "mensaje": estado.get("mensaje", ""),
                "numero_serie": estado.get("numero_serie", ""),
                "modelo": estado.get("modelo", ""),
            })
            return resultado
        try:
            with socket.create_connection((self.ip, self.port), timeout=self.timeout):
                resultado["conectado"] = True
                resultado["mensaje"] = (
                    "El equipo responde en la red local, pero la descarga debe hacerla "
                    "el agente instalado en la PC de la sede."
                )
        except OSError:
            resultado["mensaje"] = (
                "La nube no alcanza la IP privada del equipo. Instale el agente en la PC "
                "de la sede para comprobar y descargar las marcaciones."
            )
        return resultado

    def consultar_registros_locales(self):
        ahora = timezone.localtime()
        registros = MarcacionBiometrica.objects.filter(
            fecha_hora__date=ahora.date(), es_valida=True).select_related("usuario").order_by("fecha_hora", "pk")
        personas = {}
        for m in registros:
            clave = m.usuario_id or f"dni:{m.dni}"
            if clave not in personas:
                personas[clave] = {
                    "dni": m.dni, "nombre": m.usuario.nombre_completo if m.usuario else m.nombre_empleado,
                    "rol": m.usuario.rol if m.usuario else "SIN_IDENTIFICAR",
                    "rol_display": m.usuario.get_rol_display() if m.usuario else "Por identificar",
                    "agencia_sede": m.usuario.agencia_sede if m.usuario else "Por identificar",
                    "primera_marcacion": timezone.localtime(m.fecha_hora).strftime("%H:%M:%S"),
                    "tipo_evento": m.tipo_evento, "origen": m.get_origen_display(),
                    "estado_asistencia": "Con marcación hoy",
                }
        estado = obtener_estado_agente()
        comprobacion = cache.get(f"huellero_comprobacion:{self.ip}:{self.port}", {})
        return {
            "dispositivo_ip": self.ip, "dispositivo_puerto": self.port,
            "estado_dispositivo": estado.get("estado") or comprobacion.get("estado", "SIN COMPROBAR"),
            "mensaje": estado.get("mensaje") or comprobacion.get(
                "mensaje", "Instale el agente en la PC de la sede para comprobar el equipo."),
            "ultima_comprobacion": estado.get("fecha") or comprobacion.get(
                "fecha", "Sin comprobación en esta sesión del servidor"),
            "ultima_sincronizacion": estado.get("ultima_descarga", "Sin descarga confirmada desde el equipo"),
            "fecha_consulta": ahora.strftime("%d/%m/%Y %H:%M:%S"),
            "total_presentes_hoy": len(personas), "nuevas_marcaciones_sincronizadas": 0,
            "colaboradores_presentes": list(personas.values()),
            "estado_agente": estado,
            "estados_agentes": estados_por_agente(),
            "config_agente": configuracion_agente(),
        }

    def sincronizar_marcaciones_en_vivo(self):
        """Comprueba la conexión sin generar asistencia simulada."""
        conexion = self.probar_conexion()
        cache.set(f"huellero_comprobacion:{self.ip}:{self.port}", {
            "estado": "RED DISPONIBLE" if conexion["conectado"] else "SIN CONEXIÓN",
            "mensaje": conexion["mensaje"], "fecha": timezone.localtime().strftime("%d/%m/%Y %H:%M:%S"),
        }, timeout=3600)
        return self.consultar_registros_locales()
