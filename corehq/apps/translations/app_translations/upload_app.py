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
from corehq.apps.translations.app_translations.utils import (
    get_bulk_app_sheet_headers,
    get_missing_cols,
    get_unicode_dicts,
    is_form_sheet,
    is_module_sheet,
    is_modules_and_forms_sheet,
    is_single_sheet,
    update_translation_dict,
)
from corehq.apps.translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.apps.translations.app_translations.upload_form import update_app_from_form_sheet
from corehq.apps.translations.app_translations.upload_module import update_app_from_module_sheet


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


def process_bulk_app_translation_upload(app, workbook, expected_headers):
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
        error = _check_for_sheet_error(app, sheet, expected_headers, processed_sheets=processed_sheets)
        if error:
            msgs.append((messages.error, error))
            continue

        processed_sheets.add(sheet.worksheet.title)

        warnings = _check_for_sheet_warnings(app, sheet, expected_headers)
        for warning in warnings:
            msgs.append((messages.warning, warning))

        if is_single_sheet(sheet.worksheet.title):
            module_or_form = None
            modules_and_forms_rows = []
            rows = []
            for row in sheet:
                if not row['case_property'] and not row['list_or_detail'] and not row ['label']:
                    modules_and_forms_rows.append(row)
                elif module_or_form != row['menu_or_form']:
                    msgs.extend(_process_single_sheet_rows(app, module_or_form, rows))
                    module_or_form = row['menu_or_form']
                    rows = [row]
                else:
                    rows.append(row)
            msgs.extend(_process_single_sheet_rows(app, module_or_form, rows))
            msgs.extend(_process_single_sheet_rows(app, MODULES_AND_FORMS_SHEET_NAME, modules_and_forms_rows))
        else:
            msgs.extend(_process_multi_sheet_rows(app, sheet.worksheet.title, sheet, sheet_name=sheet.worksheet.title))

    msgs.append(
        (messages.success, _("App Translations Updated!"))
    )
    return msgs


def _process_multi_sheet_rows(app, identifier, rows, sheet_name=None):
    if not identifier or not rows:
        return []

    if is_modules_and_forms_sheet(identifier):
        return update_app_from_modules_and_forms_sheet(app, rows)

    if is_module_sheet(identifier):
        return update_app_from_module_sheet(app, rows, identifier)

    if is_form_sheet(identifier):
        return update_app_from_form_sheet(app, rows, identifier)

    return []


def _process_single_sheet_rows(app, identifier, rows, sheet_name=None):
    if not identifier or not rows:
        return []

    if is_modules_and_forms_sheet(identifier):
        return update_app_from_modules_and_forms_sheet(app, rows, identifying_header='menu_or_form')

    if is_module_sheet(identifier):
        return update_app_from_module_sheet(app, rows, identifier)

    if is_form_sheet(identifier):
        return update_app_from_form_sheet(app, rows, identifier)

    return []

def _check_for_sheet_error(app, sheet, headers, processed_sheets=Ellipsis):
    expected_sheets = {h[0]: h[1] for h in headers}

    if sheet.worksheet.title in processed_sheets:
        return _('Sheet "%s" was repeated. Only the first occurrence has been processed.') % sheet.worksheet.title

    expected_headers = expected_sheets.get(sheet.worksheet.title, None)
    if expected_headers is None:
        return _('Skipping sheet "%s", did not recognize title') % sheet.worksheet.title

    # TODO: display a friendlier error message if user mixed up the two types of uploads (single vs multi sheet)
    num_required_headers = 0
    if is_modules_and_forms_sheet(sheet.worksheet.title):
        num_required_headers = 2    # module or form, sheet name
    elif is_module_sheet(sheet.worksheet.title):
        num_required_headers = 2    # case property, list or detail
    elif is_form_sheet(sheet.worksheet.title):
        num_required_headers = 1    # label
    elif is_single_sheet(sheet.worksheet.title):
        num_required_headers = 4    # menu or form, case property, list or detail, label

    expected_required_headers = tuple(expected_headers[:num_required_headers])
    actual_required_headers = tuple(sheet.headers[:num_required_headers])
    if expected_required_headers != actual_required_headers:
        return _('Skipping sheet {title}: expected first columns to be {expected}').format(
            title=sheet.worksheet.title,
            expected=", ".join(expected_required_headers),
        )


def _check_for_sheet_warnings(app, sheet, headers):
    warnings = []
    expected_sheets = {h[0]: h[1] for h in headers}
    expected_headers = expected_sheets.get(sheet.worksheet.title, None)

    missing_cols = get_missing_cols(app, sheet, headers)
    extra_cols = set(sheet.headers) - set(expected_headers)

    # Backwards compatibility for old "filepath" header names
    not_missing_cols = set()
    for col in missing_cols:
        for key, legacy in (
            ('image_', 'icon_filepath_'),
            ('audio_', 'audio_filepath_'),
        ):
            for lang in app.langs:
                if key + lang in missing_cols and legacy + lang in extra_cols:
                    not_missing_cols.add(key + lang)
                    extra_cols.remove(legacy + lang)
    missing_cols = missing_cols - not_missing_cols

    if len(missing_cols) > 0:
        warnings.append((_('Sheet "%s" has fewer columns than expected. '
            'Sheet will be processed but the following translations will be unchanged: %s')
            % (sheet.worksheet.title, ", ".join(missing_cols))))

    if len(extra_cols) > 0:
        warnings.append(_('Sheet "%s" has unrecognized columns. '
            'Sheet will be processed but ignoring the following columns: %s')
            % (sheet.worksheet.title, ", ".join(extra_cols)))

    return warnings


def update_app_from_modules_and_forms_sheet(app, sheet, identifying_header='sheet_name'):
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
        identifying_text = row.get(identifying_header, '').split('_')

        if len(identifying_text) not in (1, 2):
            msgs.append((
                messages.error,
                _('Did not recognize "%s", skipping row.') % row.get(identifying_header, '')
            ))
            continue

        module_index = int(identifying_text[0].replace("module", "")) - 1
        try:
            document = app.get_module(module_index)
        except ModuleNotFoundException:
            msgs.append((
                messages.error,
                _('Invalid module in row "%s", skipping row.') % row.get(identifying_header, '')
            ))
            continue
        if len(identifying_text) == 2:
            form_index = int(identifying_text[1].replace("form", "")) - 1
            try:
                document = document.get_form(form_index)
            except FormNotFoundException:
                msgs.append((
                    messages.error,
                    _('Invalid form in row "%s", skipping row.') % row.get(identifying_header, '')
                ))
                continue

        update_translation_dict('default_', document.name, row, app.langs)

        # Update menu media
        # For backwards compatibility with previous code, accept old "filepath" header names
        for lang in app.langs:
            image_header = 'image_%s' % lang
            if image_header not in row:
                image_header = 'icon_filepath_%s' % lang
            if image_header in row:
                document.set_icon(lang, row[image_header])

            audio_header = 'audio_%s' % lang
            if audio_header not in row:
                audio_header = 'audio_filepath_%s' % lang
            if audio_header in row:
                document.set_audio(lang, row[audio_header])

    return msgs
