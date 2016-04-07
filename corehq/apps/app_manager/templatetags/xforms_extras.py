from django import template
from django.utils import html
from django.utils.safestring import mark_safe

import re

register = template.Library()

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
            suffix = lambda lang: '''
                <span class="btn btn-xs btn-info btn-langcode-preprocessed">%(lang)s</span>
            ''' % {"lang": html.escape(lang)}
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
def input_trans(name, langs=None, input_name='name'):
    template = '''
        <input type="text"
               name="{}"
               class="form-control"
               value="%(value)s"
               placeholder="%(placeholder)s" />
    '''.format(input_name)
    return _input_trans(template, name, langs=langs)


@register.simple_tag
def inline_edit_trans(name, langs=None, readOnlyClass=''):
    template = '''
        <inline-edit params="
            name: 'name',
            value: '%(value)s',
            placeholder: '%(placeholder)s',
            rows: 1,
            lang: '%(lang)s',
            readOnlyClass: '{}',
        "></inline-edit>
    '''.format(readOnlyClass)
    return _input_trans(template, name, langs=langs)


# template may have replacements for lang, placeholder, and value
def _input_trans(template, name, langs=None):
    if langs is None:
        langs = ["default"]
    options = {
        'value': '',
        'placeholder': name['en'] if 'en' in name else "Untitled",
        'lang': '',
    }
    for lang in langs:
        if lang in name:
            if langs and lang == langs[0]:
                options['value'] = name[lang]
                options['placeholder'] = ''
            else:
                options['placeholder'] = name[lang]
                options['lang'] = lang
            break
    options = {key: re.sub(r"'", "\\'", value) for (key, value) in options.iteritems()}
    return mark_safe(template % options)


@register.filter
def clean_trans(name, langs=None):
    if langs is None:
        langs = ["default"]
    return trans(name, langs, False)
