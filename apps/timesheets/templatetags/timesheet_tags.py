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
