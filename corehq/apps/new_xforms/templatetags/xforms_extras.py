from django import template
from ..views import  _tidy

register = template.Library()


@register.filter
def nice(value):
    try:
        return value['trans']['en']
    except:
        return _tidy(value['name'])