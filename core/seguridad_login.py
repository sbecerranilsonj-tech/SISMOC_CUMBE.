"""Límite de intentos de inicio de sesión por IP e identificador."""
import hashlib

from django.core.cache import cache

LIMITE = 5
DURACION = 900


def _clave(identificador, ip):
    valor = f'{ip}:{str(identificador).lower()}'.encode()
    return 'login_intentos:' + hashlib.sha256(valor).hexdigest()


def esta_bloqueado(identificador, ip):
    return cache.get(_clave(identificador, ip), 0) >= LIMITE


def registrar_intento(identificador, ip, correcto=False):
    clave = _clave(identificador, ip)
    if correcto:
        cache.delete(clave)
        return
    try:
        cache.set(clave, cache.get(clave, 0) + 1, DURACION)
    except Exception:
        # Si la caché falla, no se bloquea el acceso por un fallo de infraestructura.
        pass
