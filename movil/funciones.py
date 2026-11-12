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
    usuario = perfil.usuario
    funcion = funcion_por_area(perfil.trabajador.area if perfil.trabajador_id else '', bool(perfil.conductor_id))
    if funcion and usuario.rol in ('ADMINISTRATIVO', 'BOLETERIA', 'OPERADOR_EMBARQUE', 'CONDUCTOR') and not usuario.is_staff and not usuario.is_superuser and usuario.rol != funcion:
        usuario.rol = funcion
        usuario.save(update_fields=['rol'])
