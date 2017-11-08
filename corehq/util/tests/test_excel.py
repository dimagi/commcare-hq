from __future__ import absolute_import
import os

from django.test import SimpleTestCase

from corehq.util.test_utils import TestFileMixin
from corehq.util.workbook_json.excel import WorkbookJSONReader


class WorkbookJSONReaderTest(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_excel_formula_reading(self):
        formula_filepath = self.get_path('formula_sheet', 'xlsx')
        workbook = WorkbookJSONReader(formula_filepath)
        results = list(workbook.get_worksheet('Sheet1'))

        self.assertEqual(results[0]['formula'], 2)  # Instead of =SUM(1,1)
