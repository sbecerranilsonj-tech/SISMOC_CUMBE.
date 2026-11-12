from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django import template

register = template.Library()


@register.filter
def importe_bcp(valor):
    """Presentación BCP independiente del idioma: 316,249.48."""
    if valor is None or valor == '':
        return '0.00'
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite():
            return '—'
        return format(numero.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), ',.2f')
    except (InvalidOperation, ValueError, TypeError):
        return '—'
