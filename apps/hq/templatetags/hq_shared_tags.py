from django import template

register = template.Library()

@register.filter
def get_item(dict, key):
    '''Get an item from a dictionary or list.'''
    print "getting %s from %s" % (key, dict)
    return dict.get(key)

