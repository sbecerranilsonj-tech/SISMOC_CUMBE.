"""Funciones derivadas de la ficha, sin elevar permisos administrativos."""
from conductores.parser import normalizar


def funcion_por_area(area='', conductor=False):
    if conductor:
        return 'CONDUCTOR'
    area = normalizar(area or '')
    if area in {'VENTAS','AUXILIAR DE VENTAS','AUXILIAR VENTAS','ASISTENTE DE VENTAS','AGENTE DE VENTAS','BOLETERIA','VENDEDOR','VENDEDOR BOLETERIA'}:
        return 'BOLETERIA'
    if area in {'EMBARQUE','EMBARCADOR','ENCARGADO DE EMBARQUE','AUXILIAR DE EMBARQUE'}:
        return 'OPERADOR_EMBARQUE'
    return ''


def sincronizar_funcion(perfil):
    """Consultar el perfil no modifica la función autorizada."""
    return None
