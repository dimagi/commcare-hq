from django import template
register = template.Library()

@register.filter
def get_hash(h, key):
    return h[key]

@register.filter
def get_index(h, index):
    return h[index]