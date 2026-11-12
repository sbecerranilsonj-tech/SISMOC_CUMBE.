"""Estado de conectividad y consulta de registros persistidos del huellero."""
import socket
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from asistencia.models import MarcacionBiometrica


class ZKTecoLiveClient:
    def __init__(self, ip: Optional[str] = None, port: Optional[int] = None, timeout: int = 4):
        cfg = getattr(settings, "ZKTECO_CONFIG", {})
        self.ip = ip or cfg.get("IP", "192.168.1.201")
        self.port = port or cfg.get("PORT", 4370)
        self.timeout = timeout

    def probar_conexion(self):
        resultado = {"ip": self.ip, "puerto": self.port, "conectado": False, "modo": "HARDWARE"}
        try:
            with socket.create_connection((self.ip, self.port), timeout=self.timeout):
                resultado["conectado"] = True
                resultado["mensaje"] = "Conexión de red disponible. La descarga de marcaciones del equipo aún no está implementada."
        except OSError:
            resultado["mensaje"] = "Sin conexión con el equipo. Se muestran únicamente los registros guardados."
        return resultado

    def consultar_registros_locales(self):
        ahora = timezone.localtime()
        registros = MarcacionBiometrica.objects.filter(fecha_hora__date=ahora.date(), es_valida=True).select_related("usuario").order_by("fecha_hora", "pk")
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
        comprobacion = cache.get(f"huellero_comprobacion:{self.ip}:{self.port}", {})
        return {
            "dispositivo_ip": self.ip, "dispositivo_puerto": self.port,
            "estado_dispositivo": comprobacion.get("estado", "SIN COMPROBAR"),
            "mensaje": comprobacion.get("mensaje", "Consulte la conexión para comprobar el equipo."),
            "ultima_comprobacion": comprobacion.get("fecha", "Sin comprobación en esta sesión del servidor"),
            "ultima_sincronizacion": "Sin descarga confirmada desde el equipo",
            "fecha_consulta": ahora.strftime("%d/%m/%Y %H:%M:%S"),
            "total_presentes_hoy": len(personas), "nuevas_marcaciones_sincronizadas": 0,
            "colaboradores_presentes": list(personas.values()),
        }

    def sincronizar_marcaciones_en_vivo(self):
        """Comprueba la conexión sin generar asistencia simulada."""
        conexion = self.probar_conexion()
        cache.set(f"huellero_comprobacion:{self.ip}:{self.port}", {
            "estado": "RED DISPONIBLE" if conexion["conectado"] else "SIN CONEXIÓN",
            "mensaje": conexion["mensaje"], "fecha": timezone.localtime().strftime("%d/%m/%Y %H:%M:%S"),
        }, timeout=3600)
        return self.consultar_registros_locales()
