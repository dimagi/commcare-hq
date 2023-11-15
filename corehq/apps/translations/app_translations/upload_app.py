import io

from django.contrib import messages
from django.template.defaultfilters import linebreaksbr
from django.utils.translation import gettext as _

from CommcareTranslationChecker import validate_workbook
from CommcareTranslationChecker.exceptions import FatalError

from corehq.apps.app_manager.exceptions import (
    FormNotFoundException,
    ModuleNotFoundException,
)
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.translations.app_translations.upload_form import (
    BulkAppTranslationFormUpdater,
)
from corehq.apps.translations.app_translations.upload_module import (
    BulkAppTranslationModuleUpdater,
)
from corehq.util import ghdiff
from corehq.apps.translations.app_translations.utils import (
    BulkAppTranslationUpdater,
    get_bulk_app_sheet_headers,
    get_menu_or_form_by_sheet_name,
    get_menu_or_form_by_unique_id,
    get_unicode_dicts,
    is_form_sheet,
    is_module_sheet,
    is_modules_and_forms_sheet,
    is_single_sheet,
    is_single_sheet_workbook,
)
from corehq.apps.translations.const import (
    MODULES_AND_FORMS_SHEET_NAME,
    SINGLE_SHEET_NAME,
)
from corehq.apps.translations.exceptions import BulkAppTranslationsException
from corehq.util.files import read_workbook_content_as_file
from corehq.util.workbook_json.excel import (
    WorkbookJSONError,
    get_single_worksheet,
)


def validate_bulk_app_translation_upload(app, workbook, email, lang_to_compare, file_obj):
    from corehq.apps.translations.validator import UploadedTranslationsValidator
    msgs = UploadedTranslationsValidator(app, workbook, lang_to_compare).compare()
    checker_messages, result_wb = run_translation_checker(file_obj)
    if msgs or checker_messages:
        _email_app_translations_discrepancies(msgs, checker_messages, email, app.name, result_wb, app.domain)
        return [(messages.error, _("Issues found. You should receive an email shortly."))]
    else:
        return [(messages.success, _("No issues found."))]


def run_translation_checker(file_obj):
    translation_checker_messages = []
    result_wb = None
    try:
        result_wb, translation_checker_messages = validate_workbook(file_obj)
    except FatalError as e:
        translation_checker_messages.append(
            _("Workbook check failed to finish due to the following error : %s" % e))
    return translation_checker_messages, result_wb


def _email_app_translations_discrepancies(msgs, checker_messages, email, app_name, result_wb, domain):
    """
    :param msgs: messages for app translation discrepancies
    :param checker_messages: messages for issues found by translation checker
    :param email: email to
    :param app_name: name of the application
    :param result_wb: result wb of translation checker to attach with the email
    :param domain: name of domain the application belongs to
    """
    def form_email_content(msgs, checker_messages):
        if msgs:
            html_file_content = ghdiff.default_css
            for sheet_name, msg in msgs.items():
                html_file_content += "<strong>{}</strong>".format(sheet_name) + msg
            text_content = _("Hi, PFA file for discrepancies found for app translations.") + "\n"
        else:
            html_file_content = None
            text_content = _("Hi, No discrepancies found for app translations.") + "\n"
        if checker_messages:
            text_content += _("Issues found with the workbook are as follows :") + "\n"
            text_content += '\n'.join([_(msg) for msg in checker_messages])
        else:
            text_content += _("No issues found with the workbook.")
        return html_file_content, text_content

    def attachment(title, content, mimetype='text/html'):
        return {'title': title, 'file_obj': content, 'mimetype': mimetype}

    subject = _("App Translations Discrepancies for {}").format(app_name)
    html_file_content, text_content = form_email_content(msgs, checker_messages)
    attachments = []
    if html_file_content:
        attachments.append(attachment("{} Discrepancies.html".format(app_name), io.StringIO(html_file_content)))
    if result_wb:
        attachments.append(attachment("{} TranslationChecker.xlsx".format(app_name),
                           io.BytesIO(read_workbook_content_as_file(result_wb)), result_wb.mime_type))

    send_html_email_async.delay(subject, email, linebreaksbr(text_content), file_attachments=attachments,
                                domain=domain, use_domain_gateway=True)


def process_bulk_app_translation_upload(app, workbook, sheet_name_to_unique_id, lang=None):
    """
    Process the bulk upload file for the given app.
    We return these message tuples instead of calling them now to allow this
    function to be used independently of request objects.

    :return: Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """

    def get_expected_headers(sheet_name):
        # This function does its best to return the headers we expect, based
        # on the current app, for an uploaded sheet. If the sheet is old, it
        # might not include the unique IDs of the modules/forms. In that case
        # `sheet_name_to_unique_id` will be empty and we fall back to using the
        # name of the sheet and hope that modules/forms have not been moved
        # since the sheet was originally downloaded.
        #
        # If a user created a new sheet, or renamed a sheet, or a form/module
        # has been deleted since this sheet was downloaded, then expected
        # headers will not be found. We return an empty list, and
        # `_check_for_sheet_error()` will handle it.
        if sheet_name in sheet_name_to_unique_id:
            unique_id = sheet_name_to_unique_id[sheet_name]
            if unique_id in expected_headers_by_id:
                return expected_headers_by_id[unique_id]
        return expected_headers_by_sheet_name.get(sheet_name, [])

    msgs = []
    single_sheet = is_single_sheet_workbook(workbook)
    expected_headers_by_sheet_name = {k: v for k, v in get_bulk_app_sheet_headers(app, single_sheet=single_sheet,
                                                                                  lang=lang)}
    expected_headers_by_id = {k: v for k, v in get_bulk_app_sheet_headers(app, single_sheet=single_sheet,
                                                                          lang=lang, by_id=True)}
    processed_sheets = set()

    for sheet in workbook.worksheets:
        expected_headers = get_expected_headers(sheet.worksheet.title)
        try:
            _check_for_sheet_error(sheet, expected_headers, processed_sheets)
        except BulkAppTranslationsException as e:
            msgs.append((messages.error, str(e)))
            continue

        processed_sheets.add(sheet.worksheet.title)

        warnings = _check_for_sheet_warnings(sheet, expected_headers)
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


def get_sheet_name_to_unique_id_map(file_or_filename, lang):
    """
    Returns a map of sheet names to unique IDs, so that when modules or
    forms have been moved we can use their ID and not their (changed) name.

    This function is called before we process the upload so that we can use
    the sheet-name-to-unique-ID map to check the sheets before they are
    processed.

    `file_or_filename` is a file not a workbook because we read uploaded
    Excel files using WorkbookJSONReader, and it can only iterate sheet
    rows once. This function opens its own Reader to parse the first sheet.
    """

    def get_sheet_name():
        return MODULES_AND_FORMS_SHEET_NAME if is_multisheet() else SINGLE_SHEET_NAME

    def is_multisheet():
        return not lang

    def is_modules_and_forms_row(row):
        """
        Returns the rows about modules and forms in single-sheet uploads.
        They are the rows that include the unique IDs.
        """
        return not row['case_property'] and not row['list_or_detail'] and not row['label']

    sheet_name_to_unique_id = {}

    try:
        worksheet = get_single_worksheet(file_or_filename, title=get_sheet_name())
    except WorkbookJSONError:
        # There is something wrong with the file. The problem will happen
        # again when we try to process the upload. To preserve current
        # behaviour, just return silently.
        return sheet_name_to_unique_id

    if is_multisheet():
        rows = worksheet
    else:
        rows = (row for row in worksheet if is_modules_and_forms_row(row))

    for row in get_unicode_dicts(rows):
        sheet_name = row.get('menu_or_form', '')
        unique_id = row.get('unique_id')
        if unique_id and sheet_name not in sheet_name_to_unique_id:
            sheet_name_to_unique_id[sheet_name] = unique_id
    return sheet_name_to_unique_id


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
    modules_and_forms_rows = []
    rows = []
    for row in sheet:
        if not row['case_property'] and not row['list_or_detail'] and not row['label']:
            modules_and_forms_rows.append(row)
        elif module_or_form != row['menu_or_form']:
            msgs.extend(_process_rows(app, module_or_form, rows, names_map, lang=lang))
            module_or_form = row['menu_or_form']
            rows = [row]
        else:
            rows.append(row)
    msgs.extend(_process_rows(app, module_or_form, rows, names_map, lang=lang))
    msgs.extend(_process_rows(app, MODULES_AND_FORMS_SHEET_NAME,
                              modules_and_forms_rows, names_map, lang=lang))
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


def _check_for_sheet_error(sheet, expected_headers, processed_sheets=Ellipsis):

    if sheet.worksheet.title in processed_sheets:
        raise BulkAppTranslationsException(_('Sheet "%s" was repeated. Only the first occurrence has been '
                                             'processed.') % sheet.worksheet.title)

    if not expected_headers:
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


def _check_for_sheet_warnings(sheet, expected_headers):
    warnings = []

    missing_cols = set(expected_headers) - set(sheet.headers)
    extra_cols = set(sheet.headers) - set(expected_headers)

    if len(missing_cols) > 0:
        warnings.append((_('Sheet "{sheet}" has fewer columns than expected. Sheet will be processed but the '
            'following translations will be unchanged: {columns}').format(sheet=sheet.worksheet.title,
                                                                          columns=", ".join(missing_cols))))

    if len(extra_cols) > 0:
        warnings.append(_('Sheet "{sheet}" has unrecognized columns. Sheet will be processed but will ignore the '
            'following columns: {columns}').format(sheet=sheet.worksheet.title, columns=", ".join(extra_cols)))

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

            if not unique_id and sheet_name in self.sheet_name_to_unique_id:
                # If we don't have a value for unique_id, try to fetch it from self.sheet_name_to_unique_id
                unique_id = self.sheet_name_to_unique_id[sheet_name]

            try:
                if unique_id:
                    document = get_menu_or_form_by_unique_id(self.app, unique_id, sheet_name)
                else:
                    document = get_menu_or_form_by_sheet_name(self.app, sheet_name)
            except (ModuleNotFoundException, FormNotFoundException, ValueError) as err:
                self.msgs.append((messages.error, str(err)))
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
