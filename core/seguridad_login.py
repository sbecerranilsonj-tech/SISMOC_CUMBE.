"""Límite de intentos de inicio de sesión por IP e identificador.

A partir del quinto fallo se bloquea 5 minutos. Cada nivel de cinco fallos
adicionales duplica la espera, con tope de una hora. Un inicio de sesión
correcto limpia el contador y el bloqueo.
"""
import hashlib

from django.core.cache import cache

LIMITE = 5
BASE_SEGUNDOS = 300
MAX_SEGUNDOS = 3600
CONTADOR_TTL = 86400


def _clave(identificador, ip):
    valor = f'{ip}:{str(identificador).lower()}'.encode()
    return hashlib.sha256(valor).hexdigest()


def segundos_de_espera(intentos):
    """Espera aplicable según el número de fallos acumulados."""
    if intentos < LIMITE:
        return 0
    nivel = (intentos - LIMITE) // LIMITE
    return min(BASE_SEGUNDOS * (2 ** nivel), MAX_SEGUNDOS)


def esta_bloqueado(identificador, ip):
    return bool(cache.get('login_bloqueo:' + _clave(identificador, ip)))


def minutos_de_espera(identificador, ip):
    """Minutos del nivel de bloqueo actual, para mostrarlos al usuario."""
    intentos = cache.get('login_intentos:' + _clave(identificador, ip), 0)
    return max(1, segundos_de_espera(intentos) // 60)


def registrar_intento(identificador, ip, correcto=False):
    clave = _clave(identificador, ip)
    contador = 'login_intentos:' + clave
    bloqueo = 'login_bloqueo:' + clave
    if correcto:
        cache.delete(contador)
        cache.delete(bloqueo)
        return
    try:
        intentos = cache.get(contador, 0) + 1
        cache.set(contador, intentos, CONTADOR_TTL)
        if intentos >= LIMITE:
            cache.set(bloqueo, True, segundos_de_espera(intentos))
    except Exception:
        # Si la caché falla, no se bloquea el acceso por un fallo de infraestructura.
        pass
