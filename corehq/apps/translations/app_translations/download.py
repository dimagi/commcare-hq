import re
from collections import OrderedDict

from django.utils.encoding import force_str

from corehq import toggles
from corehq.apps.app_manager.exceptions import XFormException
from corehq.apps.app_manager.models import ReportModule
from corehq.apps.app_manager.util import module_offers_search
from corehq.apps.app_manager.xform import ItextOutput, ItextValue
from corehq.apps.translations.app_translations.utils import (
    get_form_sheet_name,
    get_menu_row,
    get_module_sheet_name,
    get_modules_and_forms_row,
)
from corehq.apps.translations.const import (
    MODULES_AND_FORMS_SHEET_NAME,
    SINGLE_SHEET_NAME,
)
from corehq.apps.translations.generators import EligibleForTransifexChecker


def get_bulk_app_single_sheet_by_name(app, lang, eligible_for_transifex_only=False):
    checker = EligibleForTransifexChecker(app)

    rows = []
    for module in app.get_modules():
        if eligible_for_transifex_only and checker.exclude_module(module):
            continue
        sheet_name = get_module_sheet_name(module)
        rows.append(get_name_menu_media_row(module, sheet_name, lang))
        for module_row in get_module_rows([lang], module, app.domain):
            if eligible_for_transifex_only:
                field_name, field_type, translation = module_row
                if checker.is_blacklisted(module.unique_id, field_type, field_name, [translation]):
                    continue
            rows.append(get_list_detail_case_property_row(module_row, sheet_name))

        for form in module.get_forms():
            if eligible_for_transifex_only and checker.exclude_form(form):
                continue
            sheet_name = get_form_sheet_name(form)
            rows.append(get_name_menu_media_row(form, sheet_name, lang))
            for label_name_media in get_form_question_label_name_media([lang], form):
                if (
                    eligible_for_transifex_only and checker.is_label_to_skip(form.unique_id, label_name_media[0])
                ):
                    continue
                rows.append(get_question_row(label_name_media, sheet_name))

    return OrderedDict({SINGLE_SHEET_NAME: rows})


def get_bulk_app_sheets_by_name(app, lang=None, eligible_for_transifex_only=False):
    """
    Data rows for bulk app translation download

    If `eligible_for_transifex_only` is True, sheets will omit
    translations that would not be sent to Transifex.
    """
    checker = EligibleForTransifexChecker(app)

    # keys are the names of sheets, values are lists of tuples representing rows
    rows = OrderedDict({MODULES_AND_FORMS_SHEET_NAME: []})

    for module in app.get_modules():
        if eligible_for_transifex_only and checker.exclude_module(module):
            continue

        langs = [lang] if lang else app.langs

        module_sheet_name = get_module_sheet_name(module)
        rows[MODULES_AND_FORMS_SHEET_NAME].append(get_modules_and_forms_row(
            row_type="Menu",
            sheet_name=module_sheet_name,
            languages=[module.name.get(lang) for lang in langs],
            media_image=[module.icon_by_language(lang) for lang in langs],
            media_audio=[module.audio_by_language(lang) for lang in langs],
            unique_id=module.unique_id,
        ))

        rows[module_sheet_name] = []
        for module_row in get_module_rows(langs, module, app.domain):
            if eligible_for_transifex_only:
                field_name, field_type, *translations = module_row
                if checker.is_blacklisted(module.unique_id, field_type, field_name, translations):
                    continue
            rows[module_sheet_name].append(module_row)

        for form in module.get_forms():
            if eligible_for_transifex_only and checker.exclude_form(form):
                continue

            form_sheet_name = get_form_sheet_name(form)
            rows[MODULES_AND_FORMS_SHEET_NAME].append(get_modules_and_forms_row(
                row_type="Form",
                sheet_name=form_sheet_name,
                languages=[form.name.get(lang) for lang in langs],
                media_image=[form.icon_by_language(lang) for lang in langs],
                media_audio=[form.audio_by_language(lang) for lang in langs],
                unique_id=form.unique_id
            ))

            rows[form_sheet_name] = []
            for label_name_media in get_form_question_label_name_media(langs, form):
                if (
                    eligible_for_transifex_only and checker.is_label_to_skip(form.unique_id, label_name_media[0])
                ):
                    continue
                rows[form_sheet_name].append(label_name_media)

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
        ] + get_menu_row([module_or_form.name.get(lang)],
                         [module_or_form.icon_by_language(lang)],
                         [module_or_form.audio_by_language(lang)]
                         ) + ['',  # video by language
                              module_or_form.unique_id, ]
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
        ] + question_label_name_media + ['']  # unique_id
    )


def get_module_rows(langs, module, domain):
    if isinstance(module, ReportModule):
        return get_module_report_rows(langs, module)

    return get_module_case_list_form_rows(langs, module) + \
        get_module_case_list_menu_item_rows(langs, module) + \
        get_module_search_command_rows(langs, module, domain) + \
        get_module_detail_rows(langs, module) + \
        get_case_search_rows(langs, module, domain)


def get_module_report_rows(langs, module):
    rows = []

    for index, config in enumerate(module.report_configs):
        header_columns = tuple(config.header.get(lang, "") for lang in langs)
        rows.append(("Report {} Display Text".format(index), 'list') + header_columns)
        if not config.use_xpath_description:
            description_columns = tuple(config.localized_description.get(lang, "") for lang in langs)
            rows.append(("Report {} Description".format(index), 'list') + description_columns)

    return rows


def get_module_case_list_form_rows(langs, module):
    if not module.case_list_form.form_id:
        return []

    return [
        ('case_list_form_label', 'list') + tuple(module.case_list_form.label.get(lang, '')
                                                 for lang in langs)
    ]


def get_module_case_list_menu_item_rows(langs, module):
    if not hasattr(module, 'case_list'):
        return []

    if not module.case_list.show:
        return []

    return [
        ('case_list_menu_item_label', 'list') + tuple(module.case_list.label.get(lang, '')
                                                      for lang in langs)
    ]


def get_module_search_command_rows(langs, module, domain):
    if not module_offers_search(module) or not toggles.USH_CASE_CLAIM_UPDATES.enabled(domain):
        return []

    rows = [
        ('search_label', 'list')
        + tuple(module.search_config.search_label.label.get(lang, '') for lang in langs),
        ('title_label', 'list')
        + tuple(module.search_config.title_label.get(lang, '') for lang in langs),
        ('description', 'list')
        + tuple(module.search_config.description.get(lang, '') for lang in langs),
    ]
    if not toggles.SPLIT_SCREEN_CASE_SEARCH.enabled(domain):
        rows.append(
            ('search_again_label', 'list') + tuple(module.search_config.search_again_label.label.get(lang, '')
                                                   for lang in langs),
        )
    return rows


def get_case_search_rows(langs, module, domain):
    if not toggles.SYNC_SEARCH_CASE_CLAIM.enabled(domain):
        return []

    ret = []
    for prop in module.search_config.properties:
        ret.append((
            (prop.name, "case_search_display") + tuple(prop.label.get(lang, "") for lang in langs)
        ))
        ret.append((
            (prop.name, "case_search_hint") + tuple(prop.hint.get(lang, "") for lang in langs)
        ))
    return ret


def get_module_detail_rows(langs, module):
    rows = []
    rows += _get_module_detail_no_items_text(langs, module)
    rows += _get_module_detail_select_text(langs, module)
    for list_or_detail, detail in [
        ("list", module.case_details.short),
        ("detail", module.case_details.long)
    ]:
        rows += get_module_detail_tabs_rows(langs, detail, list_or_detail)
        rows += get_module_detail_fields_rows(langs, detail, list_or_detail)
    return rows


def _get_module_detail_no_items_text(langs, module):
    app = module.get_app()
    short_detail = module.case_details.short
    if not (app.supports_empty_case_list_text):
        return []
    return [
        ("no_items_text", "list") + tuple(short_detail.no_items_text.get(lang, '') for lang in langs)
    ]


def _get_module_detail_select_text(langs, module):
    app = module.get_app()
    short_detail = module.case_details.short
    if not (app.supports_select_text):
        return []
    return [
        ("select_text", "list") + tuple(short_detail.select_text.get(lang, '') for lang in langs)
    ]


def get_module_detail_tabs_rows(langs, detail, list_or_detail):
    return [
        ("Tab {}".format(index), list_or_detail) + tuple(tab.header.get(lang, "") for lang in langs)
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
    if re.search(r'\benum\b', detail.format):  # enum, conditional-enum, enum-image
        field_name += " (ID Mapping Text)"
    elif detail.format == "graph":
        field_name += " (graph)"

    return (
        (field_name, list_or_detail) + tuple(detail.header.get(lang, "") for lang in langs)
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
    for key, val in detail.graph_configuration.locale_specific_config.items():
        rows.append(
            (
                key + " (graph config)",
                list_or_detail
            ) + tuple(val.get(lang, "") for lang in langs)
        )
    for i, series in enumerate(detail.graph_configuration.series):
        for key, val in series.locale_specific_config.items():
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
                        part = force_str(part)
                        part = part.replace('&', '&amp;')
                        part = part.replace('<', '&lt;')
                        part = part.replace('>', '&gt;')
                        value += part
                itext_items[text_id][(lang, value_form)] = value

    itext_items['submit_label'] = {}
    itext_items['submit_notification_label'] = {}
    for lang in langs:
        itext_items['submit_label'][(lang, 'default')] = form.get_submit_label(lang)
        itext_items['submit_notification_label'][(lang, 'default')] = form.get_submit_notification_label(lang)

    app = form.get_app()
    for text_id, values in itext_items.items():
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
        # allow empty for submit_notification_label row
        if row[0] == 'submit_notification_label' and not any(row[1:]):
            rows.append(row)

    return rows
