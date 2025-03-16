from django import template

register = template.Library()


@register.filter
def get(dictionary, key):
    """
    Gets an item from a dictionary by key.
    Usage: {{ dictionary|get:key }}
    """
    return dictionary.get(key, None) 