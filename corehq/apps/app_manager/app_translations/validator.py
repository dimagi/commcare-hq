from __future__ import absolute_import
from __future__ import unicode_literals

import six
from memoized import memoized
from corehq.apps.app_manager.app_translations import (
    expected_bulk_app_sheet_headers,
    expected_bulk_app_sheet_rows,
    get_unicode_dicts,
)
from corehq.apps.app_manager.app_translations.const import MODULES_AND_FORMS_SHEET_NAME
from django.utils.translation import ugettext_lazy as _
from six.moves import zip


COLUMNS_TO_COMPARE = {
    'module_and_form': ['Type', 'sheet_name'],
    'module': ['case_property', 'list_or_detail'],
    'form': ['label'],
}
LESS_ROW_COUNT_MISMATCH_MESSAGE = _("We found less rows than expected. Validating what was uploaded.")
MORE_ROW_COUNT_MISMATCH_MESSAGE = _("We found more rows than expected. Validating what was uploaded.")


class UploadedTranslationsValidator(object):
    """
    this compares the excel sheet uploaded with translations with what would be generated
    with current app state and flags any discrepancies found between the two
    """
    def __init__(self, app, uploaded_workbook, lang_prefix='default_'):
        self.app = app
        self.uploaded_workbook = uploaded_workbook
        self.headers = None
        self.expected_rows = None
        self.lang_prefix = lang_prefix
        self.default_language_column = self.lang_prefix + self.app.default_language

    def _generate_expected_headers_and_rows(self):
        self.headers = {h[0]: h[1] for h in expected_bulk_app_sheet_headers(self.app)}
        self.expected_rows = expected_bulk_app_sheet_rows(self.app)

    @memoized
    def _get_header_index(self, sheet_name, header):
        for index, _column_name in enumerate(self.headers[sheet_name]):
            if _column_name == header:
                return index

    def _compare_sheet(self, sheet_name, uploaded_rows, for_type):
        """
        :param uploaded_rows: dict
        :param for_type: type of sheet, module_and_forms, module, form
        :return: list of errors messages if any
        """
        columns_to_compare = COLUMNS_TO_COMPARE[for_type] + [self.default_language_column]
        expected_rows = self.expected_rows[sheet_name]
        msgs = []
        number_of_uploaded_rows = len(uploaded_rows)
        number_of_expected_rows = len(expected_rows)
        if number_of_uploaded_rows < number_of_expected_rows:
            msgs.append(six.text_type(LESS_ROW_COUNT_MISMATCH_MESSAGE))
        elif number_of_uploaded_rows > number_of_expected_rows:
            msgs.append(six.text_type(MORE_ROW_COUNT_MISMATCH_MESSAGE))

        iterate_on = [expected_rows, uploaded_rows]
        # 2 to account for the sheet header as well
        for i, (expected_row, uploaded_row) in enumerate(zip(*iterate_on), 2):
            for column_name in columns_to_compare:
                uploaded_value = uploaded_row.get(column_name)
                expected_value = expected_row[self._get_header_index(sheet_name, column_name)]
                if expected_value != uploaded_value:

                    msgs.append("For {}:{}  uploaded '{}' but expected '{}'.".format(
                        i + 2, column_name, uploaded_value, expected_value
                    ))
        return msgs

    def compare(self):
        msgs = {}
        self._generate_expected_headers_and_rows()
        for sheet in self.uploaded_workbook.worksheets:
            rows = get_unicode_dicts(sheet)
            sheet_name = sheet.worksheet.title
            if sheet_name == MODULES_AND_FORMS_SHEET_NAME:
                error_msgs = self._compare_sheet(sheet_name, rows, 'module_and_form')
            elif 'module' in sheet_name and 'form' not in sheet_name:
                error_msgs = self._compare_sheet(sheet_name, rows, 'module')
            elif 'module' in sheet_name and 'form' in sheet_name:
                error_msgs = self._compare_sheet(sheet_name, rows, 'form')
            else:
                raise Exception("Got unexpected sheet name %s" % sheet_name)
            if error_msgs:
                msgs[sheet_name] = error_msgs
        return msgs
