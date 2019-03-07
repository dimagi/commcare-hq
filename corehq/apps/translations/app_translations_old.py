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


def update_app_from_form_sheet(app, sheet):
    """
    Modify the translations of a form given a sheet of translation data.
    This does not save the changes to the DB.

    :param sheet: a WorksheetJSONReader
    :param app:
    :return:  Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    mod_text, form_text = sheet.worksheet.title.split("_")
    module_index = int(mod_text.replace("module", "")) - 1
    form_index = int(form_text.replace("form", "")) - 1
    form = app.get_module(module_index).get_form(form_index)
    rows = get_unicode_dicts(sheet)  # fetch once, because sheet.__iter__ can only be called once

    warning = _check_for_shadow_form_warning(sheet, form)
    if warning:
        return [(messages.warning, warning)]

    if form.source:
        xform = form.wrapped_xform()
    else:
        # This form is empty. Ignore it.
        return []

    try:
        itext = xform.itext_node
    except XFormException:
        # Can't do anything with this form. Ignore it.
        return []

    # Make language nodes for each language if they don't yet exist
    #
    # Currently operating under the assumption that every xForm has at least
    # one translation element, that each translation element has a text node
    # for each question and that each text node has a value node under it
    template_translation_el = None
    # Get a translation element to be used as a template for new elements
    for lang in app.langs:
        trans_el = itext.find("./{f}translation[@lang='%s']" % lang)
        if trans_el.exists():
            template_translation_el = trans_el
    assert(template_translation_el is not None)
    # Add missing translation elements
    for lang in app.langs:
        trans_el = itext.find("./{f}translation[@lang='%s']" % lang)
        if not trans_el.exists():
            new_trans_el = copy.deepcopy(template_translation_el.xml)
            new_trans_el.set('lang', lang)
            if lang != app.langs[0]:
                # If the language isn't the default language
                new_trans_el.attrib.pop('default', None)
            else:
                new_trans_el.set('default', '')
            itext.xml.append(new_trans_el)

    def _update_translation_node(new_translation, value_node, attributes=None, delete_node=True):
        if delete_node and not new_translation:
            # Remove the node if it already exists
            if value_node.exists():
                value_node.xml.getparent().remove(value_node.xml)
            return

        # Create the node if it does not already exist
        if not value_node.exists():
            e = etree.Element(
                "{f}value".format(**namespaces), attributes
            )
            text_node.xml.append(e)
            value_node = WrappedNode(e)
        # Update the translation
        value_node.xml.tail = ''
        for node in value_node.findall("./*"):
            node.xml.getparent().remove(node.xml)
        escaped_trans = escape_output_value(new_translation)
        value_node.xml.text = escaped_trans.text
        for n in escaped_trans.getchildren():
            value_node.xml.append(n)

    def _looks_like_markdown(str):
        return re.search(r'^\d+[\.\)] |^\*|~~.+~~|# |\*{1,3}\S+\*{1,3}|\[.+\]\(\S+\)', str, re.M)

    def get_markdown_node(text_node_):
        return text_node_.find("./{f}value[@form='markdown']")

    def get_value_node(text_node_):
        try:
            return next(
                n for n in text_node_.findall("./{f}value")
                if 'form' not in n.attrib or n.get('form') == 'default'
            )
        except StopIteration:
            return WrappedNode(None)

    def had_markdown(text_node_):
        """
        Returns True if a Markdown node currently exists for a translation.
        """
        markdown_node_ = get_markdown_node(text_node_)
        return markdown_node_.exists()

    def is_markdown_vetoed(text_node_):
        """
        Return True if the value looks like Markdown but there is no
        Markdown node. It means the user has explicitly told form
        builder that the value isn't Markdown.
        """
        value_node_ = get_value_node(text_node_)
        if not value_node_.exists():
            return False
        old_trans = etree.tostring(value_node_.xml, method="text", encoding="unicode").strip()
        return _looks_like_markdown(old_trans) and not had_markdown(text_node_)

    def has_translation(row_, langs):
        for lang_ in langs:
            for trans_type_ in ['default', 'image', 'audio', 'video']:
                if row_.get(_get_col_key(trans_type_, lang_)):
                    return True

    # Aggregate Markdown vetoes, and translations that currently have Markdown
    msgs = []
    vetoes = defaultdict(lambda: False)  # By default, Markdown is not vetoed for a label
    markdowns = defaultdict(lambda: False)  # By default, Markdown is not in use
    for lang in app.langs:
        # If Markdown is vetoed for one language, we apply that veto to other languages too. i.e. If a user has
        # told HQ that "**stars**" in an app's English translation is not Markdown, then we must assume that
        # "**étoiles**" in the French translation is not Markdown either.
        for row in rows:
            label_id = row['label']
            text_node = itext.find("./{f}translation[@lang='%s']/{f}text[@id='%s']" % (lang, label_id))
            vetoes[label_id] = vetoes[label_id] or is_markdown_vetoed(text_node)
            markdowns[label_id] = markdowns[label_id] or had_markdown(text_node)
    # skip labels that have no translation provided
    skip_label = set()
    if form.is_registration_form():
        for row in rows:
            if not has_translation(row, app.langs):
                skip_label.add(row['label'])
        for label in skip_label:
            msgs.append((
                messages.error,
                _("You must provide at least one translation"
                  " for the label '%s' in sheet '%s'") % (label, sheet.worksheet.title)
            ))
    # Update the translations
    missing_cols = _get_missing_cols(app, sheet)
    for lang in app.langs:
        translation_node = itext.find("./{f}translation[@lang='%s']" % lang)
        assert(translation_node.exists())

        for row in rows:
            label_id = row['label']
            if label_id in skip_label:
                continue
            text_node = translation_node.find("./{f}text[@id='%s']" % label_id)
            if not text_node.exists():
                msgs.append((
                    messages.warning,
                    _("Unrecognized translation label {0} in sheet {1}. That row"
                      " has been skipped").format(label_id, sheet.worksheet.title)
                ))
                continue

            translations = dict()
            for trans_type in ['default', 'image', 'audio', 'video']:
                try:
                    col_key = _get_col_key(trans_type, lang)
                    translations[trans_type] = row[col_key]
                except KeyError:
                    # has already been logged as unrecoginzed column
                    continue

            keep_value_node = any(v for k, v in translations.items())

            # Add or remove translations
            for trans_type, new_translation in translations.items():
                if not new_translation and col_key not in missing_cols:
                    # If the cell corresponding to the label for this question
                    # in this language is empty, fall back to another language
                    for l in app.langs:
                        key = _get_col_key(trans_type, l)
                        if key in missing_cols:
                            continue
                        fallback = row[key]
                        if fallback:
                            new_translation = fallback
                            break

                if trans_type == 'default':
                    # plaintext/Markdown
                    if _looks_like_markdown(new_translation) and not vetoes[label_id] or markdowns[label_id]:
                        # If it looks like Markdown, add it ... unless it
                        # looked like Markdown before but it wasn't. If we
                        # have a Markdown node, always keep it. FB 183536
                        _update_translation_node(
                            new_translation,
                            get_markdown_node(text_node),
                            {'form': 'markdown'},
                            # If all translations have been deleted, allow the
                            # Markdown node to be deleted just as we delete
                            # the plaintext node
                            delete_node=(not keep_value_node)
                        )
                    _update_translation_node(
                        new_translation,
                        get_value_node(text_node),
                        {'form': 'default'},
                        delete_node=(not keep_value_node)
                    )
                else:
                    # audio/video/image
                    _update_translation_node(new_translation,
                                             text_node.find("./{f}value[@form='%s']" % trans_type),
                                             {'form': trans_type})

    save_xform(app, form, etree.tostring(xform.xml))
    return msgs


def _check_for_shadow_form_warning(sheet, form):
    if isinstance(form, ShadowForm):
        return _("Found a ShadowForm at {sheet_name} with the name {name}."
            " Cannot translate ShadowForms, skipping.").format(
                sheet_name=sheet.worksheet.title,
                name=form.default_name(),
            )


def _get_missing_cols(app, sheet):
    headers = get_bulk_app_sheet_headers(app)
    expected_sheets = {h[0]: h[1] for h in headers}
    expected_columns = expected_sheets.get(sheet.worksheet.title, None)
    return set(expected_columns) - set(sheet.headers)


def escape_output_value(value):
    try:
        return etree.fromstring("<value>{}</value>".format(
            re.sub("(?<!/)>", "&gt;", re.sub("<(\s*)(?!output)", "&lt;\\1", value))
        ))
    except XMLSyntaxError:
        # if something went horribly wrong just don't bother with escaping
        element = Element('value')
        element.text = value
        return element


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
