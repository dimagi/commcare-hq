from django import template

register = template.Library()

@register.simple_tag
def translate(t, lang, langs=[]):
    for lang in [lang] + langs:
        if lang in t:
            return t[lang]

@register.filter
def trans(name, langs=["default"]):
    for lang in langs:
        if lang in name:
            return name[lang]
    # ok, nothing yet... just return anything in name
    for _, n in sorted(name.items()):
        return n

@register.filter
def format_enum(enum, langs):
    if enum:
        return ', '.join(('='.join((key, trans(val, langs))) for key, val in enum.items()))
    else:
        return ""