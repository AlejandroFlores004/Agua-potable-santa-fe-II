"""Formato de dinero compartido para que todos los montos se vean igual en la app.

Uso en templates:
    {% load money %}
    {{ invoice.total|money }}                 -> $1,079.00
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()


def format_money(value):
    """Formatea un monto con separador de miles y 2 decimales: 1079 -> "$1,079.00"."""
    try:
        amount = Decimal(str(value if value not in (None, "") else 0)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    except InvalidOperation:
        return value
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


@register.filter
def money(value):
    return format_money(value)
