# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import copy
import itertools
import re
import ghdiff
from collections import defaultdict, OrderedDict

import six
import io
from django.contrib import messages
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from lxml import etree
from lxml.etree import XMLSyntaxError, Element
from six.moves import zip

from corehq import toggles
from corehq.apps.app_manager.const import APP_TRANSLATION_UPLOAD_FAIL_MESSAGE
from corehq.apps.app_manager.exceptions import (
    FormNotFoundException,
    ModuleNotFoundException,
    XFormException)
from corehq.apps.app_manager.models import ReportModule, ShadowForm
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import namespaces, WrappedNode, ItextValue, ItextOutput
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.apps.translations.utils import is_form_sheet, is_module_sheet, is_modules_and_forms_sheet
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.workbook_json.excel import HeaderValueError, WorkbookJSONReader, JSONReaderError, \
    InvalidExcelFileException


def get_unicode_dicts(iterable):
    """
    Iterates iterable and returns a list of dictionaries with keys and values converted to Unicode

    >>> gen = ({'0': None, 2: 'two', u'3': 0xc0ffee} for i in range(3))
    >>> get_unicode_dicts(gen)
    [{u'2': u'two', u'0': None, u'3': u'12648430'},
     {u'2': u'two', u'0': None, u'3': u'12648430'},
     {u'2': u'two', u'0': None, u'3': u'12648430'}]

    """
    def none_or_unicode(val):
        return six.text_type(val) if val is not None else val

    rows = []
    for row in iterable:
        rows.append({six.text_type(k): none_or_unicode(v) for k, v in six.iteritems(row)})
    return rows


def get_app_translation_workbook(file_or_filename):
    msgs = []
    try:
        workbook = WorkbookJSONReader(file_or_filename)
    # todo: HeaderValueError does not belong here
    except (HeaderValueError, InvalidExcelFileException) as e:
        msgs.append(
            (messages.error, _(APP_TRANSLATION_UPLOAD_FAIL_MESSAGE).format(e))
        )
        return False, msgs
    except JSONReaderError as e:
        msgs.append(
            (messages.error, _(
                "App Translation Failed! There is an issue with Excel columns. Error details: {}."
            ).format(e))
        )
        return False, msgs
    return workbook, msgs


def get_modules_and_forms_row(row_type, sheet_name, languages, media_image, media_audio, unique_id):
    """
    assemble the various pieces of data that make up a row in the
    {sheet_name} sheet into a single row (a flat tuple).

    This function is meant as the single point of truth for the
    column ordering of {sheet_name}

    """.format(sheet_name=MODULES_AND_FORMS_SHEET_NAME)
    assert row_type is not None
    assert sheet_name is not None
    assert isinstance(languages, list)
    assert isinstance(media_image, list)
    assert isinstance(media_audio, list)
    assert isinstance(unique_id, six.string_types)
    soft_assert_type_text(unique_id)

    return [item if item is not None else "" for item in
            ([row_type, sheet_name] +
             get_menu_row(languages, media_image, media_audio) +
             [unique_id])]


def get_module_sheet_name(module):
    return "module{}".format(module.get_app().get_module_index(module.unique_id) + 1)


def get_form_sheet_name(form):
    module = form.get_module()
    return "_".join([
        get_module_sheet_name(module),
        "form{}".format(module.get_form_index(form.unique_id) + 1)
    ])


def get_menu_row(languages, media_image, media_audio):
    return languages + media_image + media_audio


def get_bulk_multimedia_sheet_headers(lang):
    return (('translations', (
        'menu or form',
        'case_property',         # modules only
        'detail or label',       # detail type (module) or question label (form)
        lang,                    # localized text
        'image',
        'audio',
        'video',
    )),)


def get_bulk_multimedia_sheet_rows(lang, app):
    rows = []
    for module_index, module in enumerate(app.modules):
        prefix = [get_module_sheet_name(module)]

        # Name / menu media row
        rows.append(prefix + ['', ''] + get_menu_row([module.name.get(lang)],
                                                     [module.icon_by_language(lang)],
                                                     [module.audio_by_language(lang)]))

        # Detail case properties, etc.
        for row in get_module_rows([lang], module):
            rows.append(prefix + list(row))

        for form_index, form in enumerate(module.forms):
            prefix = [get_form_sheet_name(form), '']

            # Name / menu media row
            rows.append(prefix + [''] + get_menu_row([form.name.get(lang)],
                                                     [form.icon_by_language(lang)],
                                                     [form.audio_by_language(lang)]))

            # Questions
            for row in get_form_question_rows([lang], form):
                rows.append(prefix + row)

    return rows


def get_bulk_app_sheet_headers(app, exclude_module=None, exclude_form=None):
    '''
    Returns lists representing the expected structure of bulk app translation
    Excel file uploads and downloads.

    The list will be in the form:
    [
        ["sheetname", ["column name1", "column name 2"]],
        ["sheet2 name", [...]],
        ...
    ]

    exclude_module and exclude_form are functions that take in one argument
    (form or module) and return True if the module/form should be excluded
    from the returned list
    '''
    languages_list = ['default_' + l for l in app.langs]
    audio_lang_list = ['audio_' + l for l in app.langs]
    image_lang_list = ['image_' + l for l in app.langs]
    video_lang_list = ['video_' + l for l in app.langs]

    headers = []

    # Add headers for the first sheet
    headers.append([
        MODULES_AND_FORMS_SHEET_NAME,
        get_modules_and_forms_row(
            row_type='Type',
            sheet_name='sheet_name',
            languages=languages_list,
            media_image=['icon_filepath_%s' % l for l in app.langs],
            media_audio=['audio_filepath_%s' % l for l in app.langs],
            unique_id='unique_id',
        )
    ])

    for mod_index, module in enumerate(app.get_modules()):
        if exclude_module is not None and exclude_module(module):
            continue

        sheet_name = get_module_sheet_name(module)
        headers.append([sheet_name, ['case_property', 'list_or_detail'] + languages_list])

        for form_index, form in enumerate(module.get_forms()):
            if form.form_type == 'shadow_form':
                continue
            if exclude_form is not None and exclude_form(form):
                continue

            sheet_name = get_form_sheet_name(form)
            headers.append([
                sheet_name,
                ["label"] + languages_list + audio_lang_list + image_lang_list + video_lang_list
            ])
    return headers


def get_bulk_app_sheet_rows(app, exclude_module=None, exclude_form=None):
    """
    Data rows for bulk app translation download

    exclude_module and exclude_form are functions that take in one argument
    (form or module) and return True if the module/form should be excluded
    from the returned list
    """

    # keys are the names of sheets, values are lists of tuples representing rows
    rows = OrderedDict({MODULES_AND_FORMS_SHEET_NAME: []})

    for mod_index, module in enumerate(app.get_modules()):
        if exclude_module is not None and exclude_module(module):
            continue

        module_sheet_name = get_module_sheet_name(module)
        rows[MODULES_AND_FORMS_SHEET_NAME].append(get_modules_and_forms_row(
            row_type="Module",
            sheet_name=module_sheet_name,
            languages=[module.name.get(lang) for lang in app.langs],
            media_image=[module.icon_by_language(lang) for lang in app.langs],
            media_audio=[module.audio_by_language(lang) for lang in app.langs],
            unique_id=module.unique_id,
        ))

        rows[module_sheet_name] = []
        if not isinstance(module, ReportModule):
            rows[module_sheet_name] += get_module_rows(app.langs, module)

            for form_index, form in enumerate(module.get_forms()):
                if exclude_form is not None and exclude_form(form):
                    continue

                form_sheet_name = get_form_sheet_name(form)
                rows[MODULES_AND_FORMS_SHEET_NAME].append(get_modules_and_forms_row(
                    row_type="Form",
                    sheet_name=form_sheet_name,
                    languages=[form.name.get(lang) for lang in app.langs],
                    media_image=[form.icon_by_language(lang) for lang in app.langs],
                    media_audio=[form.audio_by_language(lang) for lang in app.langs],
                    unique_id=form.unique_id
                ))

                rows[form_sheet_name] = get_form_question_rows(app.langs, form)

    return rows


def get_module_rows(langs, module):
    return get_module_case_list_form_rows(langs, module) + get_module_detail_rows(langs, module)


def get_module_case_list_form_rows(langs, module):
    if not module.case_list_form.form_id:
        return []

    return [
        ('case_list_form_label', 'list') +
        tuple(module.case_list_form.label.get(lang, '') for lang in langs)
    ]


def get_module_detail_rows(langs, module):
    rows = []
    for list_or_detail, detail in [
        ("list", module.case_details.short),
        ("detail", module.case_details.long)
    ]:
        rows += get_module_detail_tabs_rows(langs, detail, list_or_detail)
        rows += get_module_detail_fields_rows(langs, detail, list_or_detail)
    return rows


def get_module_detail_tabs_rows(langs, detail, list_or_detail):
    return [
        ("Tab {}".format(index), list_or_detail) +
        tuple(tab.header.get(lang, "") for lang in langs)
        for index, tab in enumerate(detail.tabs)
    ]


def get_module_detail_fields_rows(langs, detail, list_or_detail):
    rows = []
    for detail in detail.get_columns():
        rows.append(get_module_detail_field_row(langs, detail, list_or_detail))
        rows += get_module_detail_enum_rows(langs, detail, list_or_detail)
        rows += get_module_detail_graph_rows(langs, detail, list_or_detail)
    return rows


def get_module_detail_field_row(langs, detail, list_or_detail):
    field_name = detail.field
    if re.search(r'\benum\b', detail.format):   # enum, conditional-enum, enum-image
        field_name += " (ID Mapping Text)"
    elif detail.format == "graph":
        field_name += " (graph)"

    return (
        (field_name, list_or_detail) +
        tuple(detail.header.get(lang, "") for lang in langs)
    )


def get_module_detail_enum_rows(langs, detail, list_or_detail):
    if not re.search(r'\benum\b', detail.format):
        return []

    rows = []
    for mapping in detail.enum:
        rows.append(
            (
                mapping.key + " (ID Mapping Value)",
                list_or_detail
            ) + tuple(
                mapping.value.get(lang, "")
                for lang in langs
            )
        )
    return rows


def get_module_detail_graph_rows(langs, detail, list_or_detail):
    if detail.format != "graph":
        return []

    rows = []
    for key, val in six.iteritems(detail.graph_configuration.locale_specific_config):
        rows.append(
            (
                key + " (graph config)",
                list_or_detail
            ) + tuple(val.get(lang, "") for lang in langs)
        )
    for i, series in enumerate(detail.graph_configuration.series):
        for key, val in six.iteritems(series.locale_specific_config):
            rows.append(
                (
                    "{} {} (graph series config)".format(key, i),
                    list_or_detail
                ) + tuple(val.get(lang, "") for lang in langs)
            )
    for i, annotation in enumerate(detail.graph_configuration.annotations):
        rows.append(
            (
                "graph annotation {}".format(i + 1),
                list_or_detail
            ) + tuple(
                annotation.display_text.get(lang, "")
                for lang in langs
            )
        )
    return rows


def get_form_question_rows(langs, form):
    if form.form_type == 'shadow_form':
        return None

    rows = []

    xform = form.wrapped_xform()
    itext_items = OrderedDict()
    nodes = []
    try:
        for lang in langs:
            nodes += xform.itext_node.findall("./{f}translation[@lang='%s']" % lang)
    except XFormException:
        pass

    for translation_node in nodes:
        lang = translation_node.attrib['lang']
        for text_node in translation_node.findall("./{f}text"):
            text_id = text_node.attrib['id']
            itext_items[text_id] = itext_items.get(text_id, {})

            for value_node in text_node.findall("./{f}value"):
                value_form = value_node.attrib.get("form", "default")
                value = ''
                for part in ItextValue.from_node(value_node).parts:
                    if isinstance(part, ItextOutput):
                        value += "<output value=\"" + part.ref + "\"/>"
                    else:
                        part = force_text(part)
                        part = part.replace('&', '&amp;')
                        part = part.replace('<', '&lt;')
                        part = part.replace('>', '&gt;')
                        value += mark_safe(part)
                itext_items[text_id][(lang, value_form)] = value

    app = form.get_app()
    for text_id, values in six.iteritems(itext_items):
        row = [text_id]
        for value_form in ["default", "image", "audio", "video"]:
            # Get the fallback value for this form
            fallback = ""
            for lang in app.langs:
                fallback = values.get((lang, value_form), fallback)
                if fallback:
                    break
            # Populate the row
            for lang in langs:
                row.append(values.get((lang, value_form), fallback))
        # Don't add empty rows:
        if any(row[1:]):
            rows.append(row)

    return rows


def _update_translation_dict(prefix, language_dict, row, langs):
    # update translations as requested
    for lang in langs:
        key = '%s%s' % (prefix, lang)
        if key not in row:
            continue
        translation = row[key]
        if translation:
            language_dict[lang] = translation
        else:
            language_dict.pop(lang, None)

    # delete anything in language_dict that isn't in langs (anymore)
    for lang in language_dict.keys():
        if lang not in langs:
            language_dict.pop(lang, None)


def _get_missing_cols(app, sheet):
    headers = get_bulk_app_sheet_headers(app)
    expected_sheets = {h[0]: h[1] for h in headers}
    expected_columns = expected_sheets.get(sheet.worksheet.title, None)
    return set(expected_columns) - set(sheet.headers)


def _get_col_key(translation_type, language):
    """
    Returns the name of the column in the bulk app translation spreadsheet
    given the translation type and language
    :param translation_type: What is being translated, i.e. 'default'
    or 'image'
    :param language:
    :return:
    """
    return "%s_%s" % (translation_type, language)
