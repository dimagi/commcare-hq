import os
import tempfile

from django.test import SimpleTestCase
from openpyxl import load_workbook

from corehq.apps.export.det.schema_generator import generate_case_schema, generate_form_schema
from corehq.util.test_utils import TestFileMixin


class TestDETCaseSchema(SimpleTestCase, TestFileMixin):
    file_path = ['data', 'det']
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = cls.get_json('case_schema')

    def test_generate_from_case_schema(self):
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx') as tmp:
            generate_case_schema(self.schema, 'test', tmp)
            wb = load_workbook(filename=tmp.name)
            ws = wb.worksheets[0]
            all_data = list(ws.values)
            headings = all_data[0]
            id_row = all_data[1]
            id_row_by_heading = dict(zip(headings, id_row))
            self.assertEqual('id', id_row_by_heading['Source Field'])
            self.assertEqual('id', id_row_by_heading['Field'])
            self.assertEqual('case', id_row_by_heading['Data Source'])
            self.assertEqual('type', id_row_by_heading['Filter Name'])
            self.assertEqual('event', id_row_by_heading['Filter Value'])

            # note: subtables for actions and indices are not tested and likely broken


class TestDETFormSchema(SimpleTestCase, TestFileMixin):
    file_path = ['data', 'det']
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = cls.get_json('form_schema')

    def test_generate_from_case_schema(self):
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx') as tmp:
            generate_form_schema(self.schema, 'test', tmp)
            wb = load_workbook(filename=tmp.name)
            ws = wb.worksheets[0]
            all_data = list(ws.values)
            headings = all_data[0]
            id_row = all_data[1]
            id_row_by_heading = dict(zip(headings, id_row))
            self.assertEqual('id', id_row_by_heading['Source Field'])
            self.assertEqual('id', id_row_by_heading['Field'])
            self.assertEqual('form', id_row_by_heading['Data Source'])
            self.assertEqual('xmlns', id_row_by_heading['Filter Name'])
            self.assertEqual('http://openrosa.org/formdesigner/B4FFDB28-8240-4950-B6E2-EA26D7B0856D',
                             id_row_by_heading['Filter Value'])

            # note: subtables for repeats are not tested and likely broken
