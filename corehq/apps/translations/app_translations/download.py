# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import re
from collections import OrderedDict

import six
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe

from corehq.apps.app_manager.exceptions import XFormException
from corehq.apps.app_manager.models import ReportModule
from corehq.apps.app_manager.xform import ItextValue, ItextOutput
from corehq.apps.translations.const import MODULES_AND_FORMS_SHEET_NAME, SINGLE_SHEET_NAME
from corehq.apps.translations.app_translations.utils import (
    get_form_sheet_name,
    get_menu_row,
    get_module_sheet_name,
    get_modules_and_forms_row,
)


def get_bulk_app_single_sheet_by_name(app, lang):
    rows = []
    for module in app.modules:
        sheet_name = get_module_sheet_name(module)
        rows.append(get_name_menu_media_row(module, sheet_name, lang))
        for module_row in get_module_rows([lang], module):
            rows.append(get_list_detail_case_property_row(module_row, sheet_name))

        for form in module.get_forms():
            sheet_name = get_form_sheet_name(form)
            rows.append(get_name_menu_media_row(form, sheet_name, lang))
            for label_name_media in get_form_question_label_name_media([lang], form):
                rows.append(get_question_row(label_name_media, sheet_name))

    return OrderedDict({SINGLE_SHEET_NAME: rows})


def get_bulk_app_sheets_by_name(app, exclude_module=None, exclude_form=None):
    """
    Data rows for bulk app translation download

    exclude_module and exclude_form are functions that take in one argument
    (form or module) and return True if the module/form should be excluded
    from the returned list
    """

    # keys are the names of sheets, values are lists of tuples representing rows
    rows = OrderedDict({MODULES_AND_FORMS_SHEET_NAME: []})

    for module in app.get_modules():
        if exclude_module is not None and exclude_module(module):
            continue

        module_sheet_name = get_module_sheet_name(module)
        rows[MODULES_AND_FORMS_SHEET_NAME].append(get_modules_and_forms_row(
            row_type="Menu",
            sheet_name=module_sheet_name,
            languages=[module.name.get(lang) for lang in app.langs],
            media_image=[module.icon_by_language(lang) for lang in app.langs],
            media_audio=[module.audio_by_language(lang) for lang in app.langs],
            unique_id=module.unique_id,
        ))

        rows[module_sheet_name] = get_module_rows(app.langs, module)

        for form in module.get_forms():
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

            rows[form_sheet_name] = get_form_question_label_name_media(app.langs, form)

    return rows


def get_name_menu_media_row(module_or_form, sheet_name, lang):
    """
    Returns name / menu media row
    """
    return (
        [
            sheet_name,
            '',  # case_property
            '',  # list_or_detail
            '',  # label
        ] +
        get_menu_row(
            [module_or_form.name.get(lang)],
            [module_or_form.icon_by_language(lang)],
            [module_or_form.audio_by_language(lang)]
        ) +
        [
            '',  # video by language
            module_or_form.unique_id,
        ]
    )


def get_list_detail_case_property_row(module_row, sheet_name):
    """
    Returns case list/detail case property name
    """
    case_property, list_or_detail, name = module_row
    return [
        sheet_name,
        case_property,
        list_or_detail,
        '',  # label
        name,
        '',  # image
        '',  # audio
        '',  # video
        '',  # unique_id
    ]


def get_question_row(question_label_name_media, sheet_name):
    return (
        [
            sheet_name,
            '',  # case_property
            '',  # list_or_detail
        ] +
        question_label_name_media +
        ['']  # unique_id
    )

def get_module_rows(langs, module):
    if isinstance(module, ReportModule):
        return []

    return get_module_case_list_form_rows(langs, module) + \
        get_module_case_list_menu_item_rows(langs, module) + \
        get_module_detail_rows(langs, module)


def get_module_case_list_form_rows(langs, module):
    if not module.case_list_form.form_id:
        return []

    return [
        ('case_list_form_label', 'list') +
        tuple(module.case_list_form.label.get(lang, '') for lang in langs)
    ]


def get_module_case_list_menu_item_rows(langs, module):
    if not hasattr(module, 'case_list'):
        return []

    if not module.case_list.show:
        return []

    return [
        ('case_list_menu_item_label', 'list') +
        tuple(module.case_list.label.get(lang, '') for lang in langs)
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


def get_form_question_label_name_media(langs, form):
    """
    Returns form question label, name, and media, in given langs
    """
    if form.form_type == 'shadow_form':
        return []

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
