from django import template
from ..views import  _tidy
import simplejson

register = template.Library()


@register.filter
def nice(value):
    try:
        return value['trans']['en']
    except:
        return _tidy(value['name'])

@register.simple_tag
def translate(t, lang, langs=[]):
    for lang in [lang] + langs:
        if lang in t:
            return t[lang]

@register.filter
def trans(name, langs):
    for lang in langs:
        if lang in name:
            return name[lang]

@register.filter
def format_enum(enum, langs):
    if enum:
        return ', '.join(('='.join((key, trans(val, langs))) for key, val in enum.items()))
    else:
        return ""