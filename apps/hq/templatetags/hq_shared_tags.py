from django import template

register = template.Library()

@register.filter
def get_item(dict, key):
    '''Get an item from a dictionary.'''
    return dict.get(key)

