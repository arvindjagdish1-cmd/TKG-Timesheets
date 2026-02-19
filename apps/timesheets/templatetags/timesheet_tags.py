from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key."""
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def get_entry_hours(entry_data, line_id):
    """Get entry data for a specific line."""
    if entry_data is None:
        return {}
    return entry_data.get(line_id, {})


@register.filter
def zero_dash(value):
    """Return '-' for zero/None/empty values, otherwise round to whole number."""
    if value is None or value == "":
        return "-"
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value
    if num == 0:
        return "-"
    return f"{num:,.0f}"


@register.filter
def in_dict(dictionary, key):
    """Return True if key exists and is truthy in dictionary."""
    if dictionary is None:
        return False
    return bool(dictionary.get(key))
