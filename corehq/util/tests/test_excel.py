from __future__ import absolute_import
from __future__ import unicode_literals
import os

from django.test import SimpleTestCase

from corehq.util.test_utils import TestFileMixin
from corehq.util.workbook_json.excel import (
    get_single_worksheet,
    get_workbook,
    WorkbookJSONError,
    WorkbookJSONReader,
)


class WorkbookJSONReaderTest(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_excel_formula_reading(self):
        formula_filepath = self.get_path('formula_sheet', 'xlsx')
        workbook = WorkbookJSONReader(formula_filepath)
        results = list(workbook.get_worksheet('Sheet1'))

        self.assertEqual(results[0]['formula'], 2)  # Instead of =SUM(1,1)

    def test_get_workbook(self):
        formula_filepath = self.get_path('formula_sheet', 'xlsx')
        workbook = get_workbook(formula_filepath)
        self.assertEquals(len(workbook.worksheets), 1)
        self.assertListEqual([row['name'] for row in workbook.worksheets[0]], ['ben'])

    def test_get_workbook_bad_file(self):
        bad_filepath = self.get_path('not_excel_file', 'xlsx')
        with self.assertRaises(WorkbookJSONError):
            get_workbook(bad_filepath)

    def test_get_workbook_duplicate_columns(self):
        bad_filepath = self.get_path('duplicate_columns', 'xlsx')
        with self.assertRaises(WorkbookJSONError):
            get_workbook(bad_filepath)

    def test_get_single_worksheet(self):
        formula_filepath = self.get_path('formula_sheet', 'xlsx')
        worksheet = get_single_worksheet(formula_filepath)
        self.assertListEqual([row['name'] for row in worksheet], ['ben'])

    def test_get_single_worksheet_by_name(self):
        formula_filepath = self.get_path('formula_sheet', 'xlsx')
        worksheet = get_single_worksheet(formula_filepath, title='Sheet1')
        self.assertListEqual([row['name'] for row in worksheet], ['ben'])

    def test_get_single_worksheet_missing(self):
        formula_filepath = self.get_path('formula_sheet', 'xlsx')
        with self.assertRaises(WorkbookJSONError):
            get_single_worksheet(formula_filepath, title='NotASheet')
