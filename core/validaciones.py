"""Validaciones de dominio compartidas por formularios y servicios."""


def rango_fechas_valido(desde, hasta, max_dias=365):
    """Verdadero si `hasta` no es anterior a `desde` y la diferencia no supera `max_dias`."""
    if not desde or not hasta:
        return False
    return 0 <= (hasta - desde).days <= max_dias
