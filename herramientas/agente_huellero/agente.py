"""Agente local del huellero ZKTeco MB360.

Se ejecuta en la PC de la sede que está en la red 192.168.10.x y lee el equipo
por TCP/IP (puerto 4370). Las marcas se envían a la nube por HTTPS; la nube
nunca necesita alcanzar la IP privada del dispositivo.

Instalación:  pip install -r requirements.txt
Ejecución:    python agente.py
"""
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

try:
    from zk import ZK
except ImportError:
    sys.exit("Falta pyzk. Ejecute: pip install -r requirements.txt")

BASE = Path(__file__).resolve().parent
logger = logging.getLogger("agente_huellero")
CONFIG_PATH = BASE / "config.json"
ESTADO_PATH = BASE / "ultimo_envio.json"
PERU = ZoneInfo("America/Lima")


def cargar_config():
    if not CONFIG_PATH.exists():
        raise SystemExit("Falta config.json: copie config.example.json y pegue el token entregado por administración.")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for clave in ("api_url", "token", "ip", "puerto"):
        if not cfg.get(clave):
            raise SystemExit(f"Falta {clave} en config.json")
    if str(cfg["token"]).startswith("PEGAR_AQUI"):
        raise SystemExit("Reemplace el token de ejemplo por el valor de HUELLERO_AGENT_TOKEN entregado por administración.")
    cfg["agente_id"] = str(cfg.get("agente_id") or "PRINCIPAL")
    cfg["sede"] = str(cfg.get("sede") or cfg["agente_id"])
    return cfg


def ultimo_uid():
    if not ESTADO_PATH.exists():
        return 0
    try:
        return int(json.loads(ESTADO_PATH.read_text(encoding="utf-8")).get("uid", 0))
    except (ValueError, TypeError):
        return 0


def guardar_uid(uid, fecha):
    ESTADO_PATH.write_text(json.dumps({"uid": uid, "fecha": fecha}), encoding="utf-8")


def conectar(cfg):
    cliente = ZK(cfg["ip"], port=int(cfg["puerto"]), timeout=int(cfg.get("timeout", 5)))
    return cliente, cliente.connect()


def iso(valor):
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=PERU)
        return valor.isoformat()
    return str(valor)


def url_api(cfg, ruta):
    return cfg["api_url"].rstrip("/") + ruta


def cabeceras(cfg):
    return {
        "Authorization": "Bearer " + str(cfg["token"]),
        "X-Agente-Id": cfg["agente_id"],
    }


def consultar_comando(cfg):
    respuesta = requests.get(url_api(cfg, "/asistencia/huellero/agente/comando/"),
                             headers=cabeceras(cfg),
                             params={"agente_id": cfg["agente_id"]}, timeout=15)
    respuesta.raise_for_status()
    return respuesta.json().get("comando") or {}


def leer_marcas(cfg, desde_uid):
    _, conexion = conectar(cfg)
    try:
        registros = conexion.get_attendance() or []
        serie = ""
        total = len(registros)
        nombres = {}
        try:
            informacion = conexion.get_device_info()
            serie = getattr(informacion, "serial_number", "") or ""
        except Exception:
            pass
        try:
            for usuario in conexion.get_users() or []:
                nombres[str(usuario.user_id)] = str(usuario.name or "").strip()
        except Exception:
            pass
        nuevas = []
        for registro in registros:
            uid = int(getattr(registro, "uid", 0) or 0)
            if uid <= desde_uid:
                continue
            user_id = getattr(registro, "user_id", None)
            tipo = "ENTRADA" if int(getattr(registro, "status", 0) or 0) == 0 else "SALIDA"
            nuevas.append({
                "uid": uid,
                "user_id": user_id,
                "nombre": nombres.get(str(user_id), ""),
                "fecha_hora": iso(getattr(registro, "timestamp", None)),
                "tipo_evento": tipo,
            })
        return nuevas, serie, total
    finally:
        try:
            conexion.disconnect()
        except Exception:
            pass


def reportar(cfg, estado, marcas, serie):
    respuesta = requests.post(
        url_api(cfg, "/asistencia/huellero/agente/reportar/"),
        headers=cabeceras(cfg),
        json={"estado": estado, "marcas": marcas, "serie": serie,
              "ip": cfg["ip"], "sede": cfg["sede"], "agente_id": cfg["agente_id"],
              "numero_equipo": cfg.get("numero_equipo", 1)},
        timeout=60,
    )
    respuesta.raise_for_status()
    return respuesta.json()


def probar(cfg):
    _, conexion = conectar(cfg)
    try:
        try:
            informacion = conexion.get_device_info()
            serie = getattr(informacion, "serial_number", "") or ""
        except Exception:
            serie = ""
        return {"conectado": True, "numero_serie": serie,
                "mensaje": "Conexión comprobada con el equipo MB360."}
    finally:
        try:
            conexion.disconnect()
        except Exception:
            pass


def main():
    cfg = cargar_config()
    intervalo = int(cfg.get("intervalo", 60))
    print(f"Agente {cfg['agente_id']} ({cfg['sede']}) · equipo {cfg['ip']}:{cfg['puerto']} · API {cfg['api_url']}")
    while True:
        ahora = datetime.now(PERU).strftime("%d/%m/%Y %H:%M:%S")
        estado = {
            "ip": cfg["ip"], "puerto": int(cfg["puerto"]),
            "modelo": "MB360", "fecha": ahora, "conectado": False,
            "numero_serie": cfg.get("serie", ""), "mensaje": "",
        }
        try:
            comando = consultar_comando(cfg)
            if comando.get("tipo") == "PROBAR":
                estado.update(probar(cfg))
            marcas, serie, total = leer_marcas(cfg, ultimo_uid())
            estado["numero_serie"] = serie or estado["numero_serie"]
            estado["total_registros"] = total
            estado["ultima_descarga"] = ahora
            estado["conectado"] = True
            estado["mensaje"] = estado["mensaje"] or "Agente activo; marcaciones al día."
            resultado = reportar(cfg, estado, marcas, serie)
            aceptadas = int(resultado.get("creadas", 0)) + int(resultado.get("duplicadas", 0))
            if marcas and aceptadas >= len(marcas):
                guardar_uid(max(m["uid"] for m in marcas), ahora)
            print(f"[{ahora}] {'Conectado' if estado['conectado'] else 'Sin conexión'} · "
                  f"{len(marcas)} nuevas · {resultado.get('creadas', 0)} creadas · "
                  f"{resultado.get('duplicadas', 0)} duplicadas")
        except Exception as error:
            estado["conectado"] = False
            logger.exception("Fallo en el ciclo del agente")
            estado["mensaje"] = (
                "No se pudo completar el ciclo. Revise el registro local del agente.")
            try:
                reportar(cfg, estado, [], "")
            except Exception:
                pass
        time.sleep(intervalo)


if __name__ == "__main__":
    main()
