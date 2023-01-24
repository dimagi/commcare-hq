from django import template
from django.utils import html
from django.utils.html import format_html
from django.utils.translation import (
    gettext as _,
    gettext_lazy
)

register = template.Library()

EMPTY_LABEL = format_html('<span class="label label-info">{}</span>', gettext_lazy('Empty'))


@register.simple_tag
def translate(t, lang, langs=None):
    langs = langs or []
    for lang in [lang] + langs:
        if lang in t:
            return t[lang]


def _create_indicator_with_brackets(lang):
    return ' [%s] ' % lang


def _create_indicator_with_markup(lang):
    style = 'btn btn-xs btn-info btn-langcode-preprocessed'
    return format_html(' <span class="{}">{}</span> ', style, lang)


def _create_empty_indicator(lang):
    return ''


def _trans(name,
        langs=None,
        include_lang=True,
        use_delim=True,
        prefix=False,
        strip_tags=False,
        generates_html=False):
    langs = langs or ["default"]
    if include_lang:
        if use_delim:
            create_lang_indicator = _create_indicator_with_brackets
        else:
            create_lang_indicator = _create_indicator_with_markup
    else:
        create_lang_indicator = _create_empty_indicator

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
            affix = ("" if is_currently_set_language else create_lang_indicator(lang))
            translation_in_requested_langs = True
            break

    if not translation_in_requested_langs and len(name) > 0:
        lang, n = sorted(name.items())[0]
        n = str(n)
        affix = create_lang_indicator(lang)

    if strip_tags:
        n = html.strip_tags(n)
        affix = html.strip_tags(affix)

    pattern = '{affix}{name}' if prefix else '{name}{affix}'
    if generates_html:
        return format_html(pattern, affix=affix, name=n)
    else:
        return pattern.format(affix=affix, name=n)


@register.filter(is_safe=True)
def trans(name, langs=["default"]):
    """
    Generates a translation in the form of 'Translation [language] '
    """
    return _trans(name, langs)


@register.filter
def html_trans(name, langs=["default"]):
    """
    Generates an HTML-friendly translation, where the language is included as markup
    i.e. 'Translation <span>language</span> '
    """
    return _trans(name, langs, use_delim=False, strip_tags=True, generates_html=True) or EMPTY_LABEL


@register.filter
def html_trans_prefix(name, langs=["default"]):
    """
    Generates an HTML-friendly translation, where the language markup is prepended
    i.e. '<span>language</span> Translation'
    """
    return _trans(name, langs, use_delim=False, prefix=True, generates_html=True) or EMPTY_LABEL


@register.filter(is_safe=True)
def clean_trans(name, langs=None):
    """Produces a simple translation without any language identifier"""
    return _trans(name, langs=langs, include_lang=False)


@register.filter
def html_name(name):
    return html.strip_tags(name) or EMPTY_LABEL


@register.simple_tag
def input_trans(name, langs=None, input_name='name', input_id=None, data_bind=None, element_type='input_text'):
    if element_type == 'input_text':
        options = _get_dynamic_input_trans_options(name, langs=langs)
        template = '''
            <input type="text"
                   name="{input_name}" {input_id_attribute} {data_bind_attribute}
                   class="form-control"
                   value="{value}"
                   placeholder="{placeholder}" />
        '''
    elif element_type == 'textarea':
        options = _get_dynamic_input_trans_options(name, langs=langs, is_textarea=True)
        template = '''
            <textarea name="{input_name}" {input_id_attribute} {data_bind_attribute}
                      class="form-control vertical-resize"
                      >{value}</textarea>
        '''

    input_id_attribute = format_html("id='{}'", input_id) if input_id else ""
    data_bind_attribute = format_html("data-bind='{}'", data_bind) if data_bind else ""

    options.update({
        "input_name": input_name,
        "input_id_attribute": input_id_attribute,
        "data_bind_attribute": data_bind_attribute
    })

    return format_html(template, **options)


@register.simple_tag
def inline_edit_trans(name, langs=None, url='', saveValueName='', postSave='',
        containerClass='', iconClass='', readOnlyClass='', disallow_edit='false'):
    options = _get_dynamic_input_trans_options(name, langs=langs, allow_blank=False)
    options.update({
        'url': url,
        'saveValueName': saveValueName,
        'containerClass': containerClass,
        'iconClass': iconClass,
        'readOnlyClass': readOnlyClass,
        'postSave': postSave,
        'disallow_edit': disallow_edit
    })

    template = '''
        <inline-edit params="
            name: 'name',
            value: '{value}',
            placeholder: '{placeholder}',
            nodeName: 'input',
            lang: '{lang}',
            url: '{url}',
            saveValueName: '{saveValueName}',
            containerClass: '{containerClass}',
            iconClass: '{iconClass}',
            readOnlyClass: '{readOnlyClass}',
            postSave: {postSave},
            disallow_edit: {disallow_edit},
        "></inline-edit>
    '''
    return format_html(template, **options)


def _get_dynamic_input_trans_options(name, langs=None, allow_blank=True, is_textarea=False):
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
    if is_textarea:
        options = _escape_options(options, keys_to_html_escape=['value'])
    else:
        options = _escape_options(options)
    return options


def _escape_options(options, keys_to_html_escape: list[str] = []):
    escaped_options = {}
    for (key, value) in options.items():
        if key in keys_to_html_escape:
            escaped_options[key] = html.escape(value)
        else:
            escaped_options[key] = html.escapejs(value)
    return escaped_options
