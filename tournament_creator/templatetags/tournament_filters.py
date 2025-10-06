from django import template

register = template.Library()

@register.filter
def dict_get(dictionary, key):
    """Get a value from a dictionary using a key"""
    if not isinstance(dictionary, dict):
        return []
    return dictionary.get(key, [])
