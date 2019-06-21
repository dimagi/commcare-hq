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
    get_menu_or_form_by_sheet_name,
    get_menu_or_form_by_unique_id,
)
from corehq.apps.translations.const import MODULES_AND_FORMS_SHEET_NAME
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
    error = _check_for_workbook_error(app, workbook, expected_headers)
    if error:
        msgs.append((messages.error, error))
        return msgs

    processed_sheets = set()
    sheet_name_to_unique_id = {}
    for sheet in workbook.worksheets:
        try:
            _check_for_sheet_error(app, sheet, expected_headers, processed_sheets=processed_sheets)
        except BulkAppTranslationsException as e:
            msgs.append((messages.error, six.text_type(e)))
            continue

        processed_sheets.add(sheet.worksheet.title)

        warnings = _check_for_sheet_warnings(app, sheet, expected_headers)
        for warning in warnings:
            msgs.append((messages.warning, warning))

        if is_single_sheet(sheet.worksheet.title):
            msgs.extend(_process_single_sheet(app, sheet, names_map=sheet_name_to_unique_id, lang=lang))
        else:
            msgs.extend(_process_rows(app, sheet.worksheet.title, sheet, names_map=sheet_name_to_unique_id))

    msgs.append(
        (messages.success, _("App Translations Updated!"))
    )
    return msgs


def _process_single_sheet(app, sheet, names_map, lang=None):
    """
    A single-sheet translation file deals with only one language, and
    fits all the items to be translated onto the same sheet. All items
    share the same columns. If the column is not applicable to the row,
    it is left empty.

    :param app: The application being translated
    :param sheet: The worksheet containing the translations
    :param names_map: A map of sheet_name (like "menu1" or "menu1_form1") to
                      module/form unique_id, used to fetch a module/form
                      even if it has been moved since the worksheet was created
    :param lang: The language that the app is being translated into
    :return: A list of error messages or an empty list
    """
    msgs = []
    module_or_form = None
    # Rows pertaining to a module (e.g. case list / case detail) or a form
    # (i.e. questions). Keyed on that module/form's identifier:
    module_or_form_rows = {}
    # Rows about the app's modules and forms, like their names and unique IDs:
    modules_and_forms_rows = []
    rows = []
    for row in sheet:
        if not row['case_property'] and not row['list_or_detail'] and not row['label']:
            modules_and_forms_rows.append(row)
        elif module_or_form != row['menu_or_form']:
            module_or_form_rows[module_or_form] = rows
            module_or_form = row['menu_or_form']
            rows = [row]
        else:
            rows.append(row)
    module_or_form_rows[module_or_form] = rows
    # Process modules_and_forms_rows first to populate names_map with their unique IDs
    msgs.extend(_process_rows(app, MODULES_AND_FORMS_SHEET_NAME,
                              modules_and_forms_rows, names_map, lang=lang))
    # Then process the rows for the modules and the forms.
    for module_or_form, rows in six.iteritems(module_or_form_rows):
        msgs.extend(_process_rows(app, module_or_form, rows, names_map, lang=lang))
    return msgs


def _process_rows(app, sheet_name, rows, names_map, lang=None):
    """
    Processes the rows of a worksheet of translations.

    This is the complement of get_bulk_app_sheets_by_name() and
    get_bulk_app_single_sheet_by_name(), from
    corehq/apps/translations/app_translations/download.py, which creates
    these worksheets and rows.

    :param app: The application being translated
    :param sheet_name: The tab name of the sheet being processed.
                       e.g. "menu1", "menu1_form1", or "Menus_and_forms"
    :param rows: The rows in the worksheet
    :param names_map: A map of sheet_name to module/form unique_id, used
                      to fetch a module/form even if it has been moved
                      since the worksheet was created
    :param lang: The language that the app is being translated into
    :return: A list of error messages or an empty list
    """
    if not sheet_name or not rows:
        return []

    if is_modules_and_forms_sheet(sheet_name):
        updater = BulkAppTranslationModulesAndFormsUpdater(app, names_map, lang=lang)
        return updater.update(rows)

    if is_module_sheet(sheet_name):
        unique_id = names_map.get(sheet_name)
        try:
            updater = BulkAppTranslationModuleUpdater(app, sheet_name, unique_id, lang=lang)
        except ModuleNotFoundException:
            return [(
                messages.error,
                _('Invalid menu in row "%s", skipping row.') % sheet_name
            )]
        return updater.update(rows)

    if is_form_sheet(sheet_name):
        unique_id = names_map.get(sheet_name)
        try:
            updater = BulkAppTranslationFormUpdater(app, sheet_name, unique_id, lang=lang)
        except FormNotFoundException:
            return [(
                messages.error,
                _('Invalid form in row "%s", skipping row.') % sheet_name
            )]
        return updater.update(rows)

    return [(
        messages.error,
        _('Did not recognize "%s", skipping row.') % sheet_name
    )]


def _check_for_workbook_error(app, workbook, headers):
    if len(headers) == 1 and len(workbook.worksheets) > 1:
        return _("Expected a single sheet. If you are uploading a multi-sheet file, "
                 "please select 'All Languages'.")
    if len(headers) > 1 and len(workbook.worksheets) == 1:
        return _("File contains only one sheet. If you are uploading a single-language file, "
                 "please select a language.")


def _check_for_sheet_error(app, sheet, headers, processed_sheets=Ellipsis):
    expected_sheets = {h[0]: h[1] for h in headers}

    if sheet.worksheet.title in processed_sheets:
        raise BulkAppTranslationsException(_('Sheet "%s" was repeated. Only the first occurrence has been '
                                             'processed.') % sheet.worksheet.title)

    expected_headers = expected_sheets.get(sheet.worksheet.title, None)
    if expected_headers is None:
        raise BulkAppTranslationsException(_('Skipping sheet "%s", could not recognize title') %
                                           sheet.worksheet.title)

    num_required_headers = 0
    if is_modules_and_forms_sheet(sheet.worksheet.title):
        num_required_headers = 1    # type
    elif is_module_sheet(sheet.worksheet.title):
        num_required_headers = 2    # case property, list or detail
    elif is_form_sheet(sheet.worksheet.title):
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


def _check_for_sheet_warnings(app, sheet, headers):
    warnings = []
    expected_sheets = {h[0]: h[1] for h in headers}
    expected_headers = expected_sheets.get(sheet.worksheet.title, None)

    missing_cols = set(expected_headers) - set(sheet.headers)
    extra_cols = set(sheet.headers) - set(expected_headers)

    if len(missing_cols) > 0:
        warnings.append((_('Sheet "%s" has fewer columns than expected. '
            'Sheet will be processed but the following translations will be unchanged: %s')
            % (sheet.worksheet.title, ", ".join(missing_cols))))

    if len(extra_cols) > 0:
        warnings.append(_('Sheet "%s" has unrecognized columns. '
            'Sheet will be processed but ignoring the following columns: %s')
            % (sheet.worksheet.title, ", ".join(extra_cols)))

    return warnings


class BulkAppTranslationModulesAndFormsUpdater(BulkAppTranslationUpdater):
    def __init__(self, app, names_map, lang=None):
        super(BulkAppTranslationModulesAndFormsUpdater, self).__init__(app, lang)
        self.sheet_name_to_unique_id = names_map

    def update(self, rows):
        """
        This handles updating module/form names and menu media
        (the contents of the "Menus and forms" sheet in the multi-tab upload).
        """
        self.msgs = []
        for row in get_unicode_dicts(rows):
            sheet_name = row.get('menu_or_form', '')
            # The unique_id column is populated on the "Menus_and_forms" sheet in multi-sheet translation files,
            # and in the "name / menu media" row in single-sheet translation files.
            unique_id = row.get('unique_id')

            if unique_id and sheet_name not in self.sheet_name_to_unique_id:
                # If we have a value for unique_id, save it in self.sheet_name_to_unique_id so we can look it up
                # for rows where the unique_id column is not populated.
                self.sheet_name_to_unique_id[sheet_name] = unique_id
            elif not unique_id and sheet_name in self.sheet_name_to_unique_id:
                # If we don't have a value for unique_id, try to fetch it from self.sheet_name_to_unique_id
                unique_id = self.sheet_name_to_unique_id[sheet_name]

            try:
                if unique_id:
                    document = get_menu_or_form_by_unique_id(self.app, unique_id, sheet_name)
                else:
                    document = get_menu_or_form_by_sheet_name(self.app, sheet_name)
            except (ModuleNotFoundException, FormNotFoundException, ValueError) as err:
                self.msgs.append((messages.error, six.text_type(err)))
                continue

            self.update_translation_dict('default_', document.name, row)

            # Update menu media
            for lang in self.langs:
                image_header = 'image_%s' % lang
                if image_header in row:
                    document.set_icon(lang, row[image_header])

                audio_header = 'audio_%s' % lang
                if audio_header in row:
                    document.set_audio(lang, row[audio_header])

        return self.msgs
