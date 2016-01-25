from django import template
from django.utils import html
from django.utils.safestring import mark_safe

register = template.Library()

LANG_BUTTON = '''
    <span class="btn btn-xs btn-info btn-langcode-preprocessed%(extra_class)s"
          style="%(extra_style)s">%(lang)s</span>
'''
EMPTY_LABEL = '<span class="label label-info">Empty</span>'


@register.simple_tag
def translate(t, lang, langs=None):
    langs = langs or []
    for lang in [lang] + langs:
        if lang in t:
            return t[lang]


@register.filter
def trans(name, langs=None, include_lang=True, use_delim=True):
    langs = langs or ["default"]
    if include_lang:
        if use_delim:
            suffix = lambda lang: ' [%s]' % lang
        else:
            suffix = lambda lang: LANG_BUTTON % {"lang": html.escape(lang), "extra_class": "", "extra_style": ""}
    else:
        suffix = lambda lang: ""
    for lang in langs:
        if lang in name and name[lang]:
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


@register.simple_tag
def input_trans(name, langs=None, input_name='name', cssClass=''):
    if langs is None:
        langs = ["default"]
    template = '''
        <input type="text" name="{}" class="{}" value="%(value)s"
               placeholder="%(placeholder)s"
               style="position: relative;" />
    '''.format(input_name, cssClass)
    for lang in langs:
        if lang in name:
            if langs and lang == langs[0]:
                return template % {"value": name[lang], "placeholder": ""}
            else:
                return template % {"value": "", "placeholder": name[lang]} + \
                    LANG_BUTTON % {
                        "lang": lang,
                        "extra_class": " langcode-input",
                        "extra_style": "position: absolute; top: 6px; right: 15px"
                    }
    default = "Untitled"
    if 'en' in name:
        default = name['en']
    return mark_safe(template % {"value": "", "placeholder": default})


@register.filter
def clean_trans(name, langs=["default"]):
    return trans(name, langs, False)

@register.filter
def format_enum(enum, langs):
    if enum:
        return ', '.join(('='.join((key, trans(val, langs))) for key, val in enum.items()))
    else:
        return ""
