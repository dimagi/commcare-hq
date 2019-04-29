# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import ghdiff
import six

import io
from django.contrib import messages
from django.utils.translation import ugettext as _

from corehq.apps.app_manager.exceptions import (
    FormNotFoundException,
    ModuleNotFoundException,
)
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.translations.app_translations.utils import (
    BulkAppTranslationUpdater,
    get_unicode_dicts,
    is_form_sheet,
    is_module_sheet,
    is_modules_and_forms_sheet,
    is_single_sheet,
    is_legacy_form_sheet,
    is_legacy_module_sheet,
    get_legacy_name_map,
    get_module_or_form,
)
from corehq.apps.translations.const import LEGACY_MODULES_AND_FORMS_SHEET_NAME, MODULES_AND_FORMS_SHEET_NAME
from corehq.apps.translations.app_translations.upload_form import BulkAppTranslationFormUpdater
from corehq.apps.translations.app_translations.upload_module import BulkAppTranslationModuleUpdater
from corehq.apps.translations.exceptions import BulkAppTranslationsException


def validate_bulk_app_translation_upload(app, workbook, email, lang_to_compare):
    from corehq.apps.translations.validator import UploadedTranslationsValidator
    msgs = UploadedTranslationsValidator(app, workbook, lang_to_compare).compare()
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


def process_bulk_app_translation_upload(app, workbook, expected_headers, lang=None):
    """
    Process the bulk upload file for the given app.
    We return these message tuples instead of calling them now to allow this
    function to be used independently of request objects.

    :return: Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    msgs = []
    legacy_name_map = get_legacy_name_map(app)
    error = _check_for_workbook_error(app, workbook, expected_headers)
    if error:
        msgs.append((messages.error, error))
        return msgs

    processed_sheets = set()
    for sheet in workbook.worksheets:
        try:
            _check_for_sheet_error(app, sheet, expected_headers,
                                   legacy_name_map=legacy_name_map, processed_sheets=processed_sheets)
        except BulkAppTranslationsException as e:
            msgs.append((messages.error, six.text_type(e)))
            continue

        processed_sheets.add(sheet.worksheet.title)

        warnings = _check_for_sheet_warnings(app, sheet, expected_headers,
                                             legacy_name_map=legacy_name_map)
        for warning in warnings:
            msgs.append((messages.warning, warning))

        if is_single_sheet(sheet.worksheet.title):
            module_or_form = None
            modules_and_forms_rows = []
            rows = []
            for row in sheet:
                if not row['case_property'] and not row['list_or_detail'] and not row['label']:
                    modules_and_forms_rows.append(row)
                elif module_or_form != row['menu_or_form']:
                    msgs.extend(_process_rows(app, module_or_form, rows, lang=lang))
                    module_or_form = row['menu_or_form']
                    rows = [row]
                else:
                    rows.append(row)
            msgs.extend(_process_rows(app, module_or_form, rows, lang=lang))
            msgs.extend(_process_rows(app, MODULES_AND_FORMS_SHEET_NAME,
                                      modules_and_forms_rows, lang=lang))
        else:
            msgs.extend(_process_rows(app, sheet.worksheet.title, sheet,
                                      sheet_name=sheet.worksheet.title))

    msgs.append(
        (messages.success, _("App Translations Updated!"))
    )
    return msgs


def _process_rows(app, identifier, rows, sheet_name=None, lang=None):
    if not identifier or not rows:
        return []

    if is_modules_and_forms_sheet(identifier):
        updater = BulkAppTranslationModulesAndFormsUpdater(app, lang=lang)
        return updater.update(rows)

    if is_module_sheet(identifier) or is_legacy_module_sheet(identifier):
        try:
            updater = BulkAppTranslationModuleUpdater(app, identifier, lang=lang)
        except ModuleNotFoundException:
            return [(
                messages.error,
                _('Invalid menu in row "%s", skipping row.') % identifier
            )]
        return updater.update(rows)

    if is_form_sheet(identifier) or is_legacy_form_sheet(identifier):
        try:
            updater = BulkAppTranslationFormUpdater(app, identifier, lang=lang)
        except FormNotFoundException:
            return [(
                messages.error,
                _('Invalid form in row "%s", skipping row.') % identifier
            )]
        return updater.update(rows)

    return [(
        messages.error,
        _('Did not recognize "%s", skipping row.') % identifier
    )]


def _check_for_workbook_error(app, workbook, headers):
    if len(headers) == 1 and len(workbook.worksheets) > 1:
        return _("Expected a single sheet. If you are uploading a multi-sheet file, "
                 "please select 'All Languages'.")
    if len(headers) > 1 and len(workbook.worksheets) == 1:
        return _("File contains only one sheet. If you are uploading a single-language file, "
                 "please select a language.")


def _check_for_sheet_error(app, sheet, headers, legacy_name_map, processed_sheets=Ellipsis):
    expected_sheets = {h[0]: h[1] for h in headers}

    if sheet.worksheet.title in processed_sheets:
        raise BulkAppTranslationsException(_('Sheet "%s" was repeated. Only the first occurrence has been '
                                             'processed.') % sheet.worksheet.title)

    expected_headers = _get_expected_headers(sheet, expected_sheets, legacy_name_map)
    if expected_headers is None:
        raise BulkAppTranslationsException(_('Skipping sheet "%s", could not recognize title') %
                                           sheet.worksheet.title)

    num_required_headers = 0
    if is_modules_and_forms_sheet(sheet.worksheet.title):
        num_required_headers = 1    # type
    elif is_module_sheet(sheet.worksheet.title) or is_legacy_module_sheet(sheet.worksheet.title):
        num_required_headers = 2    # case property, list or detail
    elif is_form_sheet(sheet.worksheet.title) or is_legacy_form_sheet(sheet.worksheet.title):
        num_required_headers = 1    # label
    elif is_single_sheet(sheet.worksheet.title):
        num_required_headers = 4    # menu or form, case property, list or detail, label

    expected_required_headers = tuple(expected_headers[:num_required_headers])
    actual_required_headers = tuple(sheet.headers[:num_required_headers])
    if expected_required_headers != actual_required_headers:
        raise BulkAppTranslationsException(_('Skipping sheet {title}: expected first columns to be '
                                             '{expected}').format(
                                                 title=sheet.worksheet.title,
                                                 expected=", ".join(expected_required_headers)))


def _get_expected_headers(sheet, expected_sheets, legacy_name_map):
    if sheet.worksheet.title == LEGACY_MODULES_AND_FORMS_SHEET_NAME:
        expected_headers = expected_sheets.get(MODULES_AND_FORMS_SHEET_NAME, None)
    elif is_legacy_module_sheet(sheet.worksheet.title) or is_legacy_form_sheet(sheet.worksheet.title):
        legacy_name = sheet.worksheet.title.replace("module", "menu")
        sheet_name = legacy_name_map[legacy_name]
        expected_headers = expected_sheets.get(sheet_name, None)
    else:
        expected_headers = expected_sheets.get(sheet.worksheet.title, None)
    return expected_headers


def _check_for_sheet_warnings(app, sheet, headers, legacy_name_map):
    warnings = []
    expected_sheets = {h[0]: h[1] for h in headers}
    expected_headers = _get_expected_headers(sheet, expected_sheets, legacy_name_map)

    missing_cols = _get_missing_cols(app, sheet, headers, legacy_name_map)
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

    # Backwards compatibility for old "sheet_name" header
    extra_cols = extra_cols - {'sheet_name'}
    missing_cols = missing_cols - {'menu_or_form'}

    if len(missing_cols) > 0:
        warnings.append((_('Sheet "%s" has fewer columns than expected. '
            'Sheet will be processed but the following translations will be unchanged: %s')
            % (sheet.worksheet.title, ", ".join(missing_cols))))

    if len(extra_cols) > 0:
        warnings.append(_('Sheet "%s" has unrecognized columns. '
            'Sheet will be processed but ignoring the following columns: %s')
            % (sheet.worksheet.title, ", ".join(extra_cols)))

    return warnings


def _get_missing_cols(app, sheet, headers, legacy_name_map):
    expected_sheets = {h[0]: h[1] for h in headers}
    expected_columns = _get_expected_headers(sheet, expected_sheets, legacy_name_map)
    return set(expected_columns) - set(sheet.headers)


class BulkAppTranslationModulesAndFormsUpdater(BulkAppTranslationUpdater):
    def __init__(self, app, lang=None):
        super(BulkAppTranslationModulesAndFormsUpdater, self).__init__(app, lang)

    def get_module_or_form(self, identifier):
        try:
            return get_module_or_form(self.app, identifier)
        except ModuleNotFoundException as err:
            message = _('Invalid menu in row "%s", skipping row.') % identifier
        except FormNotFoundException as err:
            message = _('Invalid form in row "%s", skipping row.') % identifier
        except (IndexError, ValueError) as err:
            message = _('Did not recognize "%s", skipping row.') % identifier
        if message:
            raise err.__class__(message)

    def update(self, rows):
        """
        This handles updating module/form names and menu media
        (the contents of the "Menus and forms" sheet in the multi-tab upload).
        """
        self.msgs = []
        for row in get_unicode_dicts(rows):
            identifier = row.get('menu_or_form', row.get('sheet_name', ''))
            try:
                module_or_form = self.get_module_or_form(identifier)
            except (IndexError, ValueError, ModuleNotFoundException, FormNotFoundException) as err:
                self.msgs.append((messages.error, six.text_type(err)))
                continue

            self.update_translation_dict('default_', module_or_form.name, row)

            # Update menu media
            # For backwards compatibility with previous code, accept old "filepath" header names
            for lang in self.langs:
                image_header = 'image_%s' % lang
                if image_header not in row:
                    image_header = 'icon_filepath_%s' % lang
                if image_header in row:
                    module_or_form.set_icon(lang, row[image_header])

                audio_header = 'audio_%s' % lang
                if audio_header not in row:
                    audio_header = 'audio_filepath_%s' % lang
                if audio_header in row:
                    module_or_form.set_audio(lang, row[audio_header])

        return self.msgs
