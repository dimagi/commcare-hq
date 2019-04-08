# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import copy
import itertools
import re
import six
import io
from collections import defaultdict, OrderedDict

import ghdiff
from django.contrib import messages
from django.template.defaultfilters import linebreaksbr
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
from corehq.util.files import read_workbook_content_as_file
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.workbook_json.excel import HeaderValueError, WorkbookJSONReader, JSONReaderError, \
    InvalidExcelFileException
from CommcareTranslationChecker import validate_workbook
from CommcareTranslationChecker.exceptions import FatalError


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


def process_bulk_app_translation_upload(app, workbook):
    """
    Process the bulk upload file for the given app.
    We return these message tuples instead of calling them now to allow this
    function to be used independently of request objects.

    :param app:
    :param f:
    :return: Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    msgs = []

    headers = get_bulk_app_sheet_headers(app)
    expected_sheets = {h[0]: h[1] for h in headers}
    processed_sheets = set()

    for sheet in workbook.worksheets:
        # sheet.__iter__ can only be called once, so cache the result
        rows = get_unicode_dicts(sheet)

        # CHECK FOR REPEAT SHEET
        if sheet.worksheet.title in processed_sheets:
            msgs.append((
                messages.error,
                'Sheet "%s" was repeated. Only the first ' +
                'occurrence has been processed' %
                sheet.worksheet.title
            ))
            continue

        # CHECK FOR BAD SHEET NAME
        expected_columns = expected_sheets.get(sheet.worksheet.title, None)
        if expected_columns is None:
            msgs.append((
                messages.error,
                'Skipping sheet "%s", did not recognize title' %
                sheet.worksheet.title
            ))
            continue

        # CHECK FOR MISSING KEY COLUMN
        if sheet.worksheet.title == MODULES_AND_FORMS_SHEET_NAME:
            # Several columns on this sheet could be used to uniquely identify
            # rows. Using sheet_name for now, but unique_id could also be used.
            if expected_columns[1] not in sheet.headers:
                msgs.append((
                    messages.error,
                    'Skipping sheet "%s", could not find "%s" column' %
                    (sheet.worksheet.title, expected_columns[1])
                ))
                continue
        elif expected_columns[0] == "case_property":
            # It's a module sheet
            if (expected_columns[0] not in sheet.headers
                    or expected_columns[1] not in sheet.headers):
                msgs.append((
                    messages.error,
                    'Skipping sheet "%s", could not find case_property'
                    ' or list_or_detail column.' % sheet.worksheet.title
                ))
                continue
        else:
            # It's a form sheet
            if expected_columns[0] not in sheet.headers:
                msgs.append((
                    messages.error,
                    'Skipping sheet "%s", could not find label column' %
                    sheet.worksheet.title
                ))
                continue

        processed_sheets.add(sheet.worksheet.title)

        # CHECK FOR MISSING COLUMNS
        missing_cols = set(expected_columns) - set(sheet.headers)
        if len(missing_cols) > 0:
            msgs.append((
                messages.warning,
                'Sheet "%s" has fewer columns than expected. '
                'Sheet will be processed but the following'
                ' translations will be unchanged: %s'
                % (sheet.worksheet.title, " ,".join(missing_cols))
            ))

        # CHECK FOR EXTRA COLUMNS
        extra_cols = set(sheet.headers) - set(expected_columns)
        if len(extra_cols) > 0:
            msgs.append((
                messages.warning,
                'Sheet "%s" has unrecognized columns. '
                'Sheet will be processed but ignoring the following columns: %s'
                % (sheet.worksheet.title, " ,".join(extra_cols))
            ))

        # NOTE: At the moment there is no missing row detection.
        # This could be added if we want though
        #      (it is not that bad if a user leaves out a row)

        try:
            if sheet.worksheet.title == MODULES_AND_FORMS_SHEET_NAME:
                # It's the first sheet
                ms = _process_modules_and_forms_sheet(rows, app)
                msgs.extend(ms)
            elif sheet.headers[0] == "case_property":
                # It's a module sheet
                ms = _update_case_list_translations(sheet, rows, app)
                msgs.extend(ms)
            else:
                # It's a form sheet
                ms = update_form_translations(sheet, rows, missing_cols, app)
                msgs.extend(ms)
        except ValueError:
            msgs.append((messages.error, _("There was a problem loading sheet {} and was skipped.").format(
                sheet.worksheet.title)))

    msgs.append(
        (messages.success, _("App Translations Updated!"))
    )
    return msgs


def run_translation_checker(file_obj):
    translation_checker_messages = []
    result_wb = None
    try:
        result_wb = validate_workbook(file_obj, translation_checker_messages)
    except FatalError as e:
        translation_checker_messages.append(
            _("Workbook check failed to finish due to the following error : %s" % e))
    return translation_checker_messages, result_wb


def validate_bulk_app_translation_upload(app, workbook, email, file_obj, lang_to_compare):
    from corehq.apps.translations.validator import UploadedTranslationsValidator
    msgs = UploadedTranslationsValidator(app, workbook, lang_to_compare).compare()
    checker_messages, result_wb = run_translation_checker(file_obj)
    if msgs:
        _email_app_translations_discrepancies(msgs, checker_messages, email, app.name, result_wb)
        return [(messages.error, _("Issues found. You should receive an email shortly."))]
    else:
        return [(messages.success, _("No issues found."))]


def _email_app_translations_discrepancies(msgs, checker_messages, email, app_name, result_wb):
    """
    :param msgs: messages for app translation discrepancies
    :param checker_messages: messages for issues found by translation checker
    :param email: email to
    :param app_name: name of the application
    :param result_wb: result wb of translation checker to attach with the email
    """
    def _form_email_content(msgs, checker_messages):
        if msgs:
            html_content = ghdiff.default_css
            for sheet_name, msg in msgs.items():
                html_content += "<strong>{}</strong>".format(sheet_name) + msg
            text_content = _("Hi, PFA file for discrepancies found for app translations.\n")
        else:
            html_content = None
            text_content = _("Hi, No discrepancies found for app translations.\n")
        if checker_messages:
            text_content += _("Issues found with the workbook are as follows :\n %s." % '\n'.join(
                checker_messages))
        else:
            text_content += _("No issues found with the workbook.")
        return html_content, text_content

    def _attachment(title, content, mimetype='text/html'):
        return {'title': title, 'file_obj': content, 'mimetype': mimetype}

    subject = _("App Translations Discrepancies for {}").format(app_name)
    html_content, text_content = _form_email_content(msgs, checker_messages)
    attachments = []
    if html_content:
        attachments.append(_attachment("{} Discrepancies.html".format(app_name), io.StringIO(html_content)))
    if result_wb:
        attachments.append(_attachment("{} TranslationChecker.xlsx".format(app_name),
                                       io.BytesIO(read_workbook_content_as_file(result_wb)), result_wb.mime_type))
    send_html_email_async.delay(subject, email, linebreaksbr(text_content), file_attachments=attachments)


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
        if not isinstance(module, ReportModule):
            for row in get_module_rows([lang], module):
                rows.append(prefix + list(row))

            for form_index, form in enumerate(module.forms):
                prefix = [get_form_sheet_name(form), '']

                # Name / menu media row
                rows.append(prefix + [''] + get_menu_row([form.name.get(lang)],
                                                        [form.icon_by_language(lang)],
                                                        [form.audio_by_language(lang)]))

                # Questions
                if form.form_type != 'shadow_form':
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
                ["label"] + languages_list + image_lang_list + audio_lang_list + video_lang_list
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

                if form.form_type != 'shadow_form':
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


def _process_modules_and_forms_sheet(rows, app):
    """
    Modify the translations and media references for the modules and forms in
    the given app as per the data provided in rows.
    This does not save the changes to the database.
    :param rows:
    :param app:
    :return:  Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    msgs = []

    for row in rows:
        identifying_text = row.get('sheet_name', '').split('_')

        if len(identifying_text) not in (1, 2):
            msgs.append((
                messages.error,
                _('Invalid sheet_name "%s", skipping row.') % row.get(
                    'sheet_name', ''
                )
            ))
            continue

        module_index = int(identifying_text[0].replace("module", "")) - 1
        try:
            document = app.get_module(module_index)
        except ModuleNotFoundException:
            msgs.append((
                messages.error,
                _('Invalid module in row "%s", skipping row.') % row.get(
                    'sheet_name'
                )
            ))
            continue
        if len(identifying_text) == 2:
            form_index = int(identifying_text[1].replace("form", "")) - 1
            try:
                document = document.get_form(form_index)
            except FormNotFoundException:
                msgs.append((
                    messages.error,
                    _('Invalid form in row "%s", skipping row.') % row.get(
                        'sheet_name'
                    )
                ))
                continue

        _update_translation_dict('default_', document.name, row, app.langs)

        for lang in app.langs:
            icon_filepath = 'icon_filepath_%s' % lang
            audio_filepath = 'audio_filepath_%s' % lang
            if icon_filepath in row:
                document.set_icon(lang, row[icon_filepath])
            if audio_filepath in row:
                document.set_audio(lang, row[audio_filepath])

    return msgs


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


def update_form_translations(sheet, rows, missing_cols, app):
    """
    Modify the translations of a form given a sheet of translation data.
    This does not save the changes to the DB.

    :param sheet: a WorksheetJSONReader
    :param rows: The rows of the sheet (we can't get this from the sheet
    because sheet.__iter__ can only be called once)
    :param missing_cols:
    :param app:
    :return:  Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    msgs = []
    mod_text, form_text = sheet.worksheet.title.split("_")
    module_index = int(mod_text.replace("module", "")) - 1
    form_index = int(form_text.replace("form", "")) - 1
    form = app.get_module(module_index).get_form(form_index)
    if isinstance(form, ShadowForm):
        msgs.append((
            messages.warning,
            _("Found a ShadowForm at module-{module_index} form-{form_index} with the name {name}."
              " Cannot translate ShadowForms, skipping.").format(
                  # Add one to revert back to match index in Excel sheet
                  module_index=module_index + 1,
                  form_index=form_index + 1,
                  name=form.default_name(),
              )
        ))
        return msgs

    if form.source:
        xform = form.wrapped_xform()
    else:
        # This Form doesn't have an xform yet. It is empty.
        # Tell the user this?
        return msgs

    try:
        itext = xform.itext_node
    except XFormException:
        return msgs

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
                  " for the label '{0}' in sheet '{1}'").format(label, sheet.worksheet.title)
            ))
    # Update the translations
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


def escape_output_value(value):
    try:
        return etree.fromstring("<value>{}</value>".format(
            re.sub(r"(?<!/)>", "&gt;", re.sub(r"<(\s*)(?!output)", "&lt;\\1", value))
        ))
    except XMLSyntaxError:
        # if something went horribly wrong just don't bother with escaping
        element = Element('value')
        element.text = value
        return element


def _remove_description_from_case_property(row):
    return re.match('.*(?= \()', row['case_property']).group()


def _update_case_list_translations(sheet, rows, app):
    """
    Modify the translations of a module case list and detail display properties
    given a sheet of translation data. The properties in the sheet must be in
    the exact same order that they appear in the bulk app translation download.
    This function does not save the modified app to the database.

    :param sheet:
    :param rows: The rows of the sheet (we can't get this from the sheet
    because sheet.__iter__ can only be called once)
    :param app:
    :return:  Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    # The list might contain DetailColumn instances in them that have exactly
    # the same attributes (but are in different positions). Therefore we must
    # match sheet rows to DetailColumns by position.
    msgs = []

    module_index = int(sheet.worksheet.title.replace("module", "")) - 1
    module = app.get_module(module_index)

    if isinstance(module, ReportModule):
        return msgs

    # It is easier to process the translations if mapping and graph config
    # rows are nested under their respective DetailColumns.

    condensed_rows = []
    case_list_form_label = None
    detail_tab_headers = [None for i in module.case_details.long.tabs]
    index_of_last_enum_in_condensed = -1
    index_of_last_graph_in_condensed = -1

    for i, row in enumerate(rows):
        # If it's an enum case property, set index_of_last_enum_in_condensed
        if row['case_property'].endswith(" (ID Mapping Text)"):
            row['id'] = _remove_description_from_case_property(row)
            condensed_rows.append(row)
            index_of_last_enum_in_condensed = len(condensed_rows) - 1

        # If it's an enum value, add it to it's parent enum property
        elif row['case_property'].endswith(" (ID Mapping Value)"):
            row['id'] = _remove_description_from_case_property(row)
            parent = condensed_rows[index_of_last_enum_in_condensed]
            parent['mappings'] = parent.get('mappings', []) + [row]

        # If it's a graph case property, set index_of_last_graph_in_condensed
        elif row['case_property'].endswith(" (graph)"):
            row['id'] = _remove_description_from_case_property(row)
            condensed_rows.append(row)
            index_of_last_graph_in_condensed = len(condensed_rows) - 1

        # If it's a graph configuration item, add it to its parent
        elif row['case_property'].endswith(" (graph config)"):
            row['id'] = _remove_description_from_case_property(row)
            parent = condensed_rows[index_of_last_graph_in_condensed]
            parent['configs'] = parent.get('configs', []) + [row]

        # If it's a graph series configuration item, add it to its parent
        elif row['case_property'].endswith(" (graph series config)"):
            trimmed_property = _remove_description_from_case_property(row)
            row['id'] = trimmed_property.split(" ")[0]
            row['series_index'] = trimmed_property.split(" ")[1]
            parent = condensed_rows[index_of_last_graph_in_condensed]
            parent['series_configs'] = parent.get('series_configs', []) + [row]

        # If it's a graph annotation, add it to its parent
        elif row['case_property'].startswith("graph annotation "):
            row['id'] = int(row['case_property'].split(" ")[-1])
            parent = condensed_rows[index_of_last_graph_in_condensed]
            parent['annotations'] = parent.get('annotations', []) + [row]

        # It's a case list registration form label. Don't add it to condensed rows
        elif row['case_property'] == 'case_list_form_label':
            case_list_form_label = row

        # If it's a tab header, don't add it to condensed rows
        elif re.search(r'^Tab \d+$', row['case_property']):
            index = int(row['case_property'].split(' ')[-1])
            if index < len(detail_tab_headers):
                detail_tab_headers[index] = row
            else:
                msgs.append((
                    messages.error,
                    _("Expected {0} case detail tabs in sheet {1} but found row for Tab {2}. "
                      "No changes were made for sheet {1}.").format(
                          len(detail_tab_headers),
                          sheet.worksheet.title,
                          index
                      )
                ))

        # It's a normal case property
        else:
            row['id'] = row['case_property']
            condensed_rows.append(row)

    partial_upload = False
    list_rows = [
        row for row in condensed_rows if row['list_or_detail'] == 'list'
    ]
    detail_rows = [
        row for row in condensed_rows if row['list_or_detail'] == 'detail'
    ]
    short_details = list(module.case_details.short.get_columns())
    long_details = list(module.case_details.long.get_columns())

    # Check length of lists
    for expected_list, received_list, word in [
        (short_details, list_rows, "list"),
        (long_details, detail_rows, "detail")
    ]:
        if len(expected_list) != len(received_list):
            # if a field is not referenced twice in a case list or detail,
            # then we can perform a partial upload using field (case property)
            # as a key
            number_fields = len({detail.field for detail in expected_list})
            if number_fields == len(expected_list) and toggles.ICDS.enabled(app.domain):
                partial_upload = True
                continue
            msgs.append((
                messages.error,
                _("Expected {0} case {3} properties in sheet {2}, found {1}. "
                  "No case list or detail properties for sheet {2} were "
                  "updated").format(
                      len(expected_list),
                      len(received_list),
                      sheet.worksheet.title,
                      word
                  )
            ))

    if msgs:
        return msgs

    # Update the translations
    def _update_translation(row, language_dict, require_translation=True):
        ok_to_delete_translations = (
            not require_translation or _has_at_least_one_translation(
                    row, 'default', app.langs
            ))
        if ok_to_delete_translations:
            _update_translation_dict('default_', language_dict, row, app.langs)
        else:
            msgs.append((
                messages.error,
                _("You must provide at least one translation" +
                  " of the case property '%s'") % row['case_property']
            ))

    def _update_id_mappings(rows, detail):
        if len(rows) == len(detail.enum) or not toggles.ICDS.enabled(app.domain):
            for row, mapping in zip(rows, detail.enum):
                _update_translation(row, mapping.value)
        else:
            # Not all of the id mappings are described.
            # If we can identify by key, we can proceed.
            mappings_by_prop = {mapping.key: mapping for mapping in detail.enum}
            if len(detail.enum) != len(mappings_by_prop):
                msgs.append((messages.error,
                             _("You must provide all ID mappings for property '{}'")
                             .format(detail.field)))
            else:
                for row in rows:
                    if row['id'] in mappings_by_prop:
                        _update_translation(row, mappings_by_prop[row['id']].value)

    def _update_detail(row, detail):
        # Update the translations for the row and all its child rows
        _update_translation(row, detail.header)
        _update_id_mappings(row.get('mappings', []), detail)
        for i, graph_annotation_row in enumerate(row.get('annotations', [])):
            _update_translation(
                graph_annotation_row,
                detail['graph_configuration']['annotations'][i].display_text,
                False
            )
        for graph_config_row in row.get('configs', []):
            config_key = graph_config_row['id']
            _update_translation(
                graph_config_row,
                detail['graph_configuration']['locale_specific_config'][config_key],
                False
            )
        for graph_config_row in row.get('series_configs', []):
            config_key = graph_config_row['id']
            series_index = int(graph_config_row['series_index'])
            _update_translation(
                graph_config_row,
                detail['graph_configuration']['series'][series_index]['locale_specific_config'][config_key],
                False
            )

    def _update_details_based_on_position(list_rows, short_details, detail_rows, long_details):
        for row, detail in \
                itertools.chain(zip(list_rows, short_details), zip(detail_rows, long_details)):

            # Check that names match (user is not allowed to change property in the
            # upload). Mismatched names indicate the user probably botched the sheet.
            if row.get('id', None) != detail.field:
                msgs.append((
                    messages.error,
                    _('A row in sheet {sheet} has an unexpected value of "{field}" '
                      'in the case_property column. Case properties must appear in '
                      'the same order as they do in the bulk app translation '
                      'download. No translations updated for this row.').format(
                          sheet=sheet.worksheet.title,
                          field=row.get('case_property', "")
                      )
                ))
                continue
            _update_detail(row, detail)

    def _partial_upload(rows, details):
        rows_by_property = {row['id']: row for row in rows}
        for detail in details:
            if rows_by_property.get(detail.field):
                _update_detail(rows_by_property.get(detail.field), detail)

    if partial_upload:
        _partial_upload(list_rows, short_details)
        _partial_upload(detail_rows, long_details)
    else:
        _update_details_based_on_position(list_rows, short_details, detail_rows, long_details)

    for index, tab in enumerate(detail_tab_headers):
        if tab:
            _update_translation(tab, module.case_details.long.tabs[index].header)
    if case_list_form_label:
        _update_translation(case_list_form_label, module.case_list_form.label)

    return msgs


def _has_at_least_one_translation(row, prefix, langs):
    """
    Returns true if the given row has at least one translation.

    >> has_at_least_one_translation(
        {'default_en': 'Name', 'case_property': 'name'}, 'default', ['en', 'fra']
    )
    true
    >> has_at_least_one_translation(
        {'case_property': 'name'}, 'default', ['en', 'fra']
    )
    false

    :param row:
    :param prefix:
    :param langs:
    :return:
    """
    return any(row.get(prefix + '_' + l) for l in langs)


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
