from django import template
from django.utils import html
from django.utils.safestring import mark_safe

register = template.Library()

LANG_BUTTON = ' <a href="#" style="color: #FFFFFF; text-decoration:none;" class="btn btn-mini btn-inverse btn-langcode-preprocessed%(extra_class)s">%(lang)s</a>'
EMPTY_LABEL = '<span class="label label-info">Empty</span>'

@register.simple_tag
def translate(t, lang, langs=[]):
    for lang in [lang] + langs:
        if lang in t:
            return t[lang]

@register.filter
def trans(name, langs=["default"], include_lang=True, use_delim=True):
    if include_lang:
        if use_delim:
            suffix = lambda lang: ' [%s]' % lang
        else:
            suffix = lambda lang: LANG_BUTTON % {"lang": html.escape(lang), "extra_class": ""}
    else:
        suffix = lambda lang: ""
    for lang in langs:
        if lang in name:
            return name[lang] + ("" if langs and lang == langs[0] else suffix(lang))
        # ok, nothing yet... just return anything in name
    for lang, n in sorted(name.items()):
        return n + suffix(lang)
    return ""

@register.filter
def html_trans(name, langs=["default"]):
    return mark_safe(trans(name, langs, use_delim=False) or EMPTY_LABEL)

@register.filter
def html_name(name):
    return mark_safe(name or EMPTY_LABEL)

@register.filter
def input_trans(name, langs=["default"]):
    template='<input class="wide" type="text" name="name" value="%(value)s" placeholder="%(placeholder)s" />'
    for lang in langs:
        if lang in name:
            if langs and lang == langs[0]:
                return template % {"value": name[lang], "placeholder": ""}
            else:
                return template % {"value": "", "placeholder": name[lang]} + \
                       LANG_BUTTON % {"lang": lang, "extra_class": " langcode-input"}
    default = "Untitled"
    if 'en' in name:
        default = name['en']
    return template % {"value": "", "placeholder": default }

@register.filter
def clean_trans(name, langs=["default"]):
    return trans(name, langs, False)

@register.filter
def format_enum(enum, langs):
    if enum:
        return ', '.join(('='.join((key, trans(val, langs))) for key, val in enum.items()))
    else:
        return ""