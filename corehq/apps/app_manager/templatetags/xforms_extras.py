from django import template
from django.utils import html
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

register = template.Library()

EMPTY_LABEL = mark_safe('<span class="label label-info">Empty</span>')  # nosec: no user input


@register.simple_tag
def translate(t, lang, langs=None):
    langs = langs or []
    for lang in [lang] + langs:
        if lang in t:
            return t[lang]


def tag_with_brackets(lang):
    return ' [%s] ' % lang


def tag_with_markup(lang):
    style = 'btn btn-xs btn-info btn-langcode-preprocessed'
    return format_html(' <span class="{}">{}</span> ', style, lang)


def empty_tag(lang):
    return ''


@register.filter
def trans(name, langs=None, include_lang=True, use_delim=True, prefix=False, strip_tags=False):
    langs = langs or ["default"]
    if include_lang:
        if use_delim:
            tag = tag_with_brackets
        else:
            tag = tag_with_markup
    else:
        tag = empty_tag

    translation_in_requested_langs = False
    n = ''
    affix = ''

    for lang in langs:
        # "name[lang] is not None" added to avoid empty lang tag in case of empty value for a field.
        # When a value like {'en': ''} is passed to trans it returns [en] which then gets added
        # as value on the input field and is visible in the text box.
        # Ref: https://github.com/dimagi/commcare-hq/pull/16871/commits/14453f4482f6580adc9619a8ad3efb39d5cf37a2
        if lang in name and name[lang] is not None:
            n = str(name[lang])
            is_currently_set_language = langs and lang == langs[0]
            affix = ("" if is_currently_set_language else tag(lang))
            translation_in_requested_langs = True
            break

    if not translation_in_requested_langs and len(name) > 0:
        lang, n = sorted(name.items())[0]
        n = str(n)
        affix = tag(lang)

    if strip_tags:
        n = html.strip_tags(n)
        affix = html.strip_tags(affix)

    pattern = '{affix}{name}' if prefix else '{name}{affix}'
    return format_html(pattern, affix=affix, name=n)


@register.filter
def html_trans(name, langs=["default"]):
    return trans(name, langs, use_delim=False, strip_tags=True) or EMPTY_LABEL


@register.filter
def html_trans_prefix(name, langs=["default"]):
    return trans(name, langs, use_delim=False, prefix=True) or EMPTY_LABEL


@register.filter
def html_trans_prefix_delim(name, langs=["default"]):
    return trans(name, langs, use_delim=True, prefix=True) or EMPTY_LABEL


@register.filter
def html_name(name):
    return mark_safe(html.strip_tags(name) or EMPTY_LABEL)


@register.simple_tag
def input_trans(name, langs=None, input_name='name', input_id=None, data_bind=None):
    template = '''
        <input type="text"
               name="{}" {} {}
               class="form-control"
               value="%(value)s"
               placeholder="%(placeholder)s" />
    '''.format(
        input_name,
        f"id='{input_id}'" if input_id else "",
        f"data-bind='{data_bind}'" if data_bind else "")
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
    options = {key: html.escapejs(value) for (key, value) in options.items()}
    return mark_safe(template % options)


@register.filter
def clean_trans(name, langs=None):
    return trans(name, langs=langs, include_lang=False)
