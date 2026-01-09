from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


@register.filter
def multiply(value, arg):
    """Multiply a numeric value by arg using Decimal for accuracy.

    Returns an empty string for invalid input so templates can handle
    formatting with `floatformat` or display fallbacks.
    """
    try:
        if value is None:
            return ''
        val = Decimal(str(value))
        factor = Decimal(str(arg))
        return val * factor
    except (InvalidOperation, TypeError, ValueError):
        return ''
