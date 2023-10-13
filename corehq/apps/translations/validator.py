from django.utils.translation import gettext as _

from memoized import memoized

from corehq.apps.translations.app_translations.download import (
    get_bulk_app_sheets_by_name,
    get_bulk_app_single_sheet_by_name,
)
from corehq.apps.translations.app_translations.utils import (
    get_bulk_app_sheet_headers,
    get_unicode_dicts,
    is_form_sheet,
    is_module_sheet,
    is_modules_and_forms_sheet,
    is_single_sheet_workbook,
)
from corehq.apps.translations.const import (
    MODULES_AND_FORMS_SHEET_NAME,
    SINGLE_SHEET_NAME,
    SINGLE_SHEET_STATIC_HEADERS,
)
from corehq.apps.translations.exceptions import BulkAppTranslationsException
from corehq.apps.translations.generators import (
    AppTranslationsGenerator,
    Unique_ID,
)
from corehq.util import ghdiff

COLUMNS_TO_COMPARE = {
    'module_and_form': ['Type', 'menu_or_form'],
    'module': ['case_property', 'list_or_detail'],
    'form': ['label'],
}
# return from ghdiff in case of no differences
NO_GHDIFF_MESSAGE = ghdiff.diff([], [], css=False)


class UploadedTranslationsValidator(object):
    """
    this compares the excel sheet uploaded with translations with what would be generated
    with current app state and flags any discrepancies found between the two
    """
    def __init__(self, app, uploaded_workbook, lang_to_compare, lang_prefix='default_'):
        self.app = app
        self.uploaded_workbook = uploaded_workbook
        self.uploaded_headers = dict()  # sheet_name: list of headers
        self.current_headers = dict()  # module_or_form_id: list of headers
        self.current_rows = dict()  # module_or_form_id: translations
        self.lang_prefix = lang_prefix
        self.default_language_column = self.lang_prefix + self.app.default_language
        self.lang_to_compare = lang_to_compare or self.app.default_language
        self.single_sheet = False
        self._setup()

    def _setup(self):
        self._validate_sheet()
        self.single_sheet = is_single_sheet_workbook(self.uploaded_workbook)
        self.lang_cols_to_compare = [self.lang_prefix + self.lang_to_compare]
        if self.lang_to_compare != self.app.default_language:
            default_lang_col = self.lang_prefix + self.app.default_language
            if default_lang_col in self.uploaded_workbook.worksheets[0].fieldnames:
                self.lang_cols_to_compare.append(default_lang_col)
        self.app_translation_generator = AppTranslationsGenerator(
            self.app.domain, self.app.get_id, None, self.app.default_language, self.lang_to_compare,
            self.lang_prefix)
        self.current_sheet_name_to_module_or_form_type_and_id = dict()
        self.uploaded_sheet_name_to_module_or_form_type_and_id = dict()

    def _validate_sheet(self):
        lang_col = self.lang_prefix + self.lang_to_compare
        if lang_col not in self.uploaded_workbook.worksheets[0].fieldnames:
            raise BulkAppTranslationsException(
                _("Missing translations for {} in uploaded sheet").format(self.lang_to_compare))

    def _generate_current_headers_and_rows(self):
        lang = self.lang_to_compare if len(self.lang_cols_to_compare) == 1 else None
        self.current_headers = {
            mod_or_form_id: headers
            for mod_or_form_id, headers in
            get_bulk_app_sheet_headers(
                self.app,
                lang=lang,
                eligible_for_transifex_only=True,
                single_sheet=self.single_sheet,
            )
        }
        if self.single_sheet:
            # single sheet supports only single language
            self.current_rows = get_bulk_app_single_sheet_by_name(
                self.app,
                self.lang_to_compare,
                eligible_for_transifex_only=True
            )
        else:
            self.current_rows = get_bulk_app_sheets_by_name(
                self.app,
                lang,
                eligible_for_transifex_only=True
            )
            self._set_current_sheet_name_to_module_or_form_mapping()
            self._map_ids_to_headers()
            self._map_ids_to_translations()

    def _set_current_sheet_name_to_module_or_form_mapping(self):
        # iterate the first sheet to get unique ids for forms/modules
        all_module_and_form_details = self.current_rows[MODULES_AND_FORMS_SHEET_NAME]
        sheet_name_column_index = self._get_current_header_index(MODULES_AND_FORMS_SHEET_NAME, 'menu_or_form')
        unique_id_column_index = self._get_current_header_index(MODULES_AND_FORMS_SHEET_NAME, 'unique_id')
        type_column_index = self._get_current_header_index(MODULES_AND_FORMS_SHEET_NAME, 'Type')
        for row in all_module_and_form_details:
            self.current_sheet_name_to_module_or_form_type_and_id[row[sheet_name_column_index]] = Unique_ID(
                row[type_column_index],
                row[unique_id_column_index]
            )

    def _map_ids_to_headers(self):
        sheet_names = list(self.current_headers.keys())
        for sheet_name in sheet_names:
            if sheet_name != MODULES_AND_FORMS_SHEET_NAME:
                mapping = self.current_sheet_name_to_module_or_form_type_and_id.get(sheet_name)
                self.current_headers[mapping.id] = self.current_headers.pop(sheet_name)

    def _map_ids_to_translations(self):
        sheet_names = list(self.current_rows.keys())
        for sheet_name in sheet_names:
            if sheet_name != MODULES_AND_FORMS_SHEET_NAME:
                mapping = self.current_sheet_name_to_module_or_form_type_and_id.get(sheet_name)
                self.current_rows[mapping.id] = self.current_rows.pop(sheet_name)

    @memoized
    def _get_current_header_index(self, module_or_form_id, header):
        if module_or_form_id not in self.current_headers:
            raise BulkAppTranslationsException(_(
                f"Could not find a module or form with ID '{module_or_form_id}' in app '{self.app.name}'"
            ))
        for index, _column_name in enumerate(self.current_headers[module_or_form_id]):
            if _column_name == header:
                return index

    def _filter_rows(self, for_type, rows, module_or_form_id):
        if for_type == 'form':
            return self.app_translation_generator.filter_invalid_rows_for_form(
                rows,
                module_or_form_id,
                self._get_current_header_index(module_or_form_id, 'label')
            )
        elif for_type == 'module':
            return self.app_translation_generator.filter_invalid_rows_for_module(
                rows,
                module_or_form_id,
                self._get_current_header_index(module_or_form_id, 'case_property'),
                self._get_current_header_index(module_or_form_id, 'list_or_detail'),
                self._get_current_header_index(module_or_form_id, self.default_language_column)
            )
        elif for_type == 'module_and_form':
            return rows
        assert False, "Unexpected type"

    def _compare_sheet(self, module_or_form_id, uploaded_rows, for_type):
        """
        :param uploaded_rows: dict
        :param for_type: type of sheet, module_and_forms, module, form
        :return: diff generated by ghdiff or None
        """
        columns_to_compare = COLUMNS_TO_COMPARE[for_type] + self.lang_cols_to_compare
        header_indices = {
            column_name: self._get_current_header_index(module_or_form_id, column_name)
            for column_name in columns_to_compare
        }
        if None in header_indices.values():
            raise BulkAppTranslationsException(_("Could not find column(s) '{}'").format(
                ", ".join([str(k) for k, v in header_indices.items() if v is None])
            ))

        if module_or_form_id not in self.current_rows:
            return self._missing_module_or_form_diff(for_type)
        if self.lang_prefix + self.app.default_language in self.lang_cols_to_compare:
            current_rows = self._filter_rows(for_type, self.current_rows[module_or_form_id], module_or_form_id)
        else:
            current_rows = self.current_rows[module_or_form_id]

        parsed_current_rows = []
        parsed_uploaded_rows = []
        for current_row in current_rows:
            parsed_current_rows.append(
                [current_row[header_indices[column_name]] for column_name in columns_to_compare]
            )
        for uploaded_row in uploaded_rows:
            parsed_uploaded_rows.append([uploaded_row.get(column_name) for column_name in columns_to_compare])

        return self._generate_diff(parsed_current_rows, parsed_uploaded_rows)

    @memoized
    def _missing_module_or_form_diff(self, for_type):
        return ghdiff.diff(_('{} not found').format(for_type), [], css=False)

    @staticmethod
    def _generate_diff(parsed_current_rows, parsed_uploaded_rows):
        current_rows_as_string = '\n'.join([', '.join(row) for row in parsed_current_rows])
        uploaded_rows_as_string = '\n'.join([', '.join(row) for row in parsed_uploaded_rows])
        diff = ghdiff.diff(current_rows_as_string, uploaded_rows_as_string, css=False)
        if diff == NO_GHDIFF_MESSAGE:
            return None
        return diff

    def compare(self):
        self._generate_current_headers_and_rows()
        if self.single_sheet:
            return self._compare_single_sheet()
        else:
            return self._compare_multiple_sheets()

    def _compare_single_sheet(self):
        sheet = self.uploaded_workbook.worksheets[0]
        columns_to_compare = SINGLE_SHEET_STATIC_HEADERS + self.lang_cols_to_compare
        parsed_expected_rows = self._processed_single_sheet_expected_rows(self.current_rows[sheet.title],
                                                                          columns_to_compare)
        parsed_uploaded_rows = self._processed_single_sheet_uploaded_rows(get_unicode_dicts(sheet),
                                                                          columns_to_compare)
        error_msgs = self._generate_diff(parsed_expected_rows, parsed_uploaded_rows)
        return {sheet.title: error_msgs} if error_msgs else {}

    def _processed_single_sheet_expected_rows(self, expected_rows, columns_to_compare):
        parsed_expected_rows = []
        for expected_row in expected_rows:
            _parsed_row = []
            for column_name in columns_to_compare:
                column_value = expected_row[self._get_current_header_index(SINGLE_SHEET_NAME, column_name)]
                if column_value is None:
                    column_value = ''
                _parsed_row.append(column_value)
            parsed_expected_rows.append(_parsed_row)
        return parsed_expected_rows

    @staticmethod
    def _processed_single_sheet_uploaded_rows(uploaded_rows, columns_to_compare):
        return [
            [uploaded_row.get(column_name) for column_name in columns_to_compare]
            for uploaded_row in uploaded_rows
        ]

    def _compare_multiple_sheets(self):
        msgs = {}
        sheets_rows = self._parse_uploaded_worksheet()
        for sheet_name in sheets_rows:
            if sheet_name == MODULES_AND_FORMS_SHEET_NAME:
                uploaded_module_or_form_id = MODULES_AND_FORMS_SHEET_NAME
            else:
                uploaded_module_or_form_id = self.uploaded_sheet_name_to_module_or_form_type_and_id[sheet_name].id
            rows = sheets_rows[sheet_name]
            if is_modules_and_forms_sheet(sheet_name):
                error_msgs = self._compare_sheet(uploaded_module_or_form_id, rows, 'module_and_form')
            elif is_module_sheet(sheet_name):
                error_msgs = self._compare_sheet(uploaded_module_or_form_id, rows, 'module')
            elif is_form_sheet(sheet_name):
                error_msgs = self._compare_sheet(uploaded_module_or_form_id, rows, 'form')
            else:
                raise Exception("Got unexpected sheet name %s" % sheet_name)
            if error_msgs:
                msgs[sheet_name] = error_msgs
        return msgs

    def _parse_uploaded_worksheet(self):
        sheets_rows = dict()
        for sheet in self.uploaded_workbook.worksheets:
            sheets_rows[sheet.worksheet.title] = get_unicode_dicts(sheet)
        self._generate_uploaded_headers()
        self._set_uploaded_sheet_name_to_module_or_form_mapping(sheets_rows[MODULES_AND_FORMS_SHEET_NAME])
        return sheets_rows

    def _generate_uploaded_headers(self):
        for sheet in self.uploaded_workbook.worksheets:
            self.uploaded_headers[sheet.title] = sheet.headers

    def _set_uploaded_sheet_name_to_module_or_form_mapping(self, all_module_and_form_details):
        for row in all_module_and_form_details:
            self.uploaded_sheet_name_to_module_or_form_type_and_id[row['menu_or_form']] = Unique_ID(
                row['Type'],
                row['unique_id']
            )
