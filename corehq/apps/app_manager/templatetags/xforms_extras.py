from __future__ import absolute_import
from __future__ import unicode_literals
from django import template
from django.utils import html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
import six

register = template.Library()

EMPTY_LABEL = '<span class="label label-info">Empty</span>'


@register.simple_tag
def translate(t, lang, langs=None):
    langs = langs or []
    for lang in [lang] + langs:
        if lang in t:
            return t[lang]


@register.filter
def trans(name, langs=None, include_lang=True, use_delim=True, prefix=False, escape=False):
    langs = langs or ["default"]
    if include_lang:
        if use_delim:
            tag = lambda lang: ' [%s] ' % lang
        else:
            tag = lambda lang: '''
                <span class="btn btn-xs btn-info btn-langcode-preprocessed">%(lang)s</span>
            ''' % {"lang": html.escape(lang)}
    else:
        tag = lambda lang: ""
    for lang in langs:
        # "name[lang] is not None" added to avoid empty lang tag in case of empty value for a field.
        # When a value like {'en': ''} is passed to trans it returns [en] which then gets added
        # as value on the input field and is visible in the text box.
        # Ref: https://github.com/dimagi/commcare-hq/pull/16871/commits/14453f4482f6580adc9619a8ad3efb39d5cf37a2
        if lang in name and name[lang] is not None:
            n = six.text_type(name[lang])
            if escape:
                n = html.escape(n)
            affix = ("" if langs and lang == langs[0] else tag(lang))
            return affix + n if prefix else n + affix
        # ok, nothing yet... just return anything in name
    for lang, n in sorted(name.items()):
        n = six.text_type(n)
        if escape:
            n = html.escape(n)
        affix = tag(lang)
        return affix + n if prefix else n + affix
    return ""


@register.filter
def html_trans(name, langs=["default"]):
    return mark_safe(html.strip_tags(trans(name, langs, use_delim=False)) or EMPTY_LABEL)


@register.filter
def html_trans_prefix(name, langs=["default"]):
    return mark_safe(trans(name, langs, use_delim=False, prefix=True, escape=True) or EMPTY_LABEL)


@register.filter
def html_trans_prefix_delim(name, langs=["default"]):
    return mark_safe(trans(name, langs, use_delim=True, prefix=True, escape=True) or EMPTY_LABEL)


@register.filter
def html_name(name):
    return mark_safe(html.strip_tags(name) or EMPTY_LABEL)


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
def inline_edit_trans(name, langs=None, url='', saveValueName='', postSave='',
        containerClass='', iconClass='', readOnlyClass='', disallow_edit='false'):
    template = '''
        <inline-edit params="
            name: 'name',
            value: '%(value)s',
            placeholder: '%(placeholder)s',
            nodeName: 'input',
            lang: '%(lang)s',
            url: '{}',
            saveValueName: '{}',
            containerClass: '{}',
            iconClass: '{}',
            readOnlyClass: '{}',
            postSave: {},
            disallow_edit: {},
        "></inline-edit>
    '''.format(url, saveValueName, containerClass, iconClass, readOnlyClass, postSave, disallow_edit)
    return _input_trans(template, name, langs=langs, allow_blank=False)


# template may have replacements for lang, placeholder, and value
def _input_trans(template, name, langs=None, allow_blank=True):
    if langs is None:
        langs = ["default"]
    placeholder = _("Untitled")
    if 'en' in name and (allow_blank or name['en'] != ''):
        placeholder = name['en']
    options = {
        'value': '',
        'placeholder': placeholder,
        'lang': '',
    }
    for lang in langs:
        if lang in name:
            if langs and lang == langs[0]:
                options['value'] = name[lang]
                options['placeholder'] = '' if allow_blank else placeholder
            else:
                options['placeholder'] = name[lang] if (allow_blank or name[lang] != '') else placeholder
                options['lang'] = lang
            break
    options = {key: html.escapejs(value) for (key, value) in six.iteritems(options)}
    return mark_safe(template % options)


@register.filter
def clean_trans(name, langs=None):
    return trans(name, langs=langs, include_lang=False)
