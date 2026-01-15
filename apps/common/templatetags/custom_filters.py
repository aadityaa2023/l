from django import template
from decimal import Decimal

register = template.Library()


@register.filter(name='multiply')
def multiply(value, arg):
    """
    Multiplies the value by the argument.
    Usage: {{ value|multiply:arg }}
    """
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except (ValueError, TypeError, AttributeError):
        return 0


@register.filter(name='percentage')
def percentage(value, total):
    """
    Calculate percentage.
    Usage: {{ value|percentage:total }}
    """
    try:
        if not total or total == 0:
            return 0
        return round((Decimal(str(value)) / Decimal(str(total))) * 100, 1)
    except (ValueError, TypeError, AttributeError, ZeroDivisionError):
        return 0
