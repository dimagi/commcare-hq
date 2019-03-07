# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import ghdiff

import io
from django.contrib import messages
from django.utils.translation import ugettext as _

from corehq.apps.app_manager.exceptions import (
    FormNotFoundException,
    ModuleNotFoundException,
)
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.translations.app_translations_old import (
    get_bulk_app_sheet_headers,
    get_unicode_dicts,
    update_app_from_form_sheet,
    _get_missing_cols,  # TODO: rename
    _update_translation_dict,   # TODO: rename
)
from corehq.apps.translations.app_translations.upload_module import update_app_from_module_sheet
from corehq.apps.translations.utils import is_form_sheet, is_module_sheet, is_modules_and_forms_sheet


def validate_bulk_app_translation_upload(app, workbook, email):
    from corehq.apps.translations.validator import UploadedTranslationsValidator
    msgs = UploadedTranslationsValidator(app, workbook).compare()
    if msgs:
        _email_app_translations_discrepancies(msgs, email, app.name)
        return [(messages.error, _("Issues found. You should receive an email shortly."))]
    else:
        return [(messages.success, _("No issues found."))]


def _email_app_translations_discrepancies(msgs, email, app_name):
    html_content = ghdiff.default_css
    for sheet_name, msg in msgs.items():
        html_content += "<strong>{}</strong>".format(sheet_name) + msg

    subject = _("App Translations Discrepancies for {}").format(app_name)
    text_content = _("Hi, PFA file for discrepancies found for app translations.")
    html_attachment = {
        'title': "{} Discrepancies.html".format(app_name),
        'file_obj': io.StringIO(html_content),
        'mimetype': 'text/html',
    }
    send_html_email_async.delay(subject, email, text_content, file_attachments=[html_attachment])


def process_bulk_app_translation_upload(app, workbook):
    """
    Process the bulk upload file for the given app.
    We return these message tuples instead of calling them now to allow this
    function to be used independently of request objects.

    :return: Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    msgs = []

    processed_sheets = set()
    for sheet in workbook.worksheets:
        error = _check_for_sheet_error(app, sheet, processed_sheets=processed_sheets)
        if error:
            msgs.append(messages.error, error)
            continue

        processed_sheets.add(sheet.worksheet.title)

        warnings = _check_for_sheet_warnings(app, sheet)
        for warning in warnings:
            msgs.append(messages.warning, warning)

        if is_modules_and_forms_sheet(sheet):
            ms = update_app_from_modules_and_forms_sheet(app, sheet)
            msgs.extend(ms)
        elif is_module_sheet(sheet):
            ms = update_app_from_module_sheet(app, sheet)
            msgs.extend(ms)
        elif is_form_sheet(sheet):
            ms = update_app_from_form_sheet(app, sheet)
            msgs.extend(ms)

    msgs.append(
        (messages.success, _("App Translations Updated!"))
    )
    return msgs


def _check_for_sheet_error(app, sheet, processed_sheets=Ellipsis):
    headers = get_bulk_app_sheet_headers(app)
    expected_sheets = {h[0]: h[1] for h in headers}

    if sheet.worksheet.title in processed_sheets:
        return _('Sheet "%s" was repeated. Only the first occurrence has been processed.') % sheet.worksheet.title

    expected_columns = expected_sheets.get(sheet.worksheet.title, None)
    if expected_columns is None:
        return _('Skipping sheet "%s", did not recognize title') % sheet.worksheet.title

    if is_modules_and_forms_sheet(sheet):
        if expected_columns[1] not in sheet.headers:
            return (_('Skipping sheet "%s", could not find "%s" column')
                % (sheet.worksheet.title, expected_columns[1]))
    elif is_module_sheet(sheet):
        if (expected_columns[0] not in sheet.headers or expected_columns[1] not in sheet.headers):
            return (_('Skipping sheet "%s", could not find case_property or list_or_detail column.')
                % sheet.worksheet.title)
    elif is_form_sheet(sheet):
        if expected_columns[0] not in sheet.headers:
            return _('Skipping sheet "%s", could not find label column') % sheet.worksheet.title


def _check_for_sheet_warnings(app, sheet):
    warnings = []
    headers = get_bulk_app_sheet_headers(app)
    expected_sheets = {h[0]: h[1] for h in headers}
    expected_columns = expected_sheets.get(sheet.worksheet.title, None)

    missing_cols = _get_missing_cols(app, sheet)
    if len(missing_cols) > 0:
        warnings.append((_('Sheet "%s" has fewer columns than expected. '
            'Sheet will be processed but the following translations will be unchanged: %s')
            % (sheet.worksheet.title, " ,".join(missing_cols))))

    extra_cols = set(sheet.headers) - set(expected_columns)
    if len(extra_cols) > 0:
        warnings.append(_('Sheet "%s" has unrecognized columns. '
            'Sheet will be processed but ignoring the following columns: %s')
            % (sheet.worksheet.title, " ,".join(extra_cols)))

    return warnings


def process_bulk_multimedia_translation_upload(app, workbook, lang):
    msgs = []
    # TODO: validate header is the right language code
    msgs.append(
        (messages.success, _("Multimedia Translations Updated in {}!".format(lang)))
    )
    return msgs


def update_app_from_modules_and_forms_sheet(app, sheet):
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

    for row in get_unicode_dicts(sheet):
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
