import os
import tempfile
from io import BytesIO

from django.test import SimpleTestCase
from openpyxl import load_workbook

from corehq.apps.export.det.exceptions import DETConfigError
from corehq.apps.export.det.schema_generator import (
    generate_from_form_export_instance,
    generate_from_case_export_instance,
    _transform_path_for_case_properties,
)
from corehq.apps.export.models import FormExportInstance, CaseExportInstance
from corehq.util.test_utils import TestFileMixin


class TestDETFCaseInstance(SimpleTestCase, TestFileMixin):
    file_path = ['data', 'det']
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.export_instance = CaseExportInstance.wrap(cls.get_json('case_export_instance'))

    def test_empty(self):
        old_tables = self.export_instance.tables
        self.export_instance.tables = []
        with self.assertRaises(DETConfigError):
            generate_from_case_export_instance(self.export_instance, BytesIO())
        self.export_instance.tables = old_tables

    def test_generate_from_case_schema(self):
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx') as tmp:
            generate_from_case_export_instance(self.export_instance, tmp)
            wb = load_workbook(filename=tmp.name)
            ws = wb.worksheets[0]
            all_data = list(ws.values)
            headings = all_data.pop(0)
            data_by_headings = [dict(zip(headings, row)) for row in all_data]
            id_row = data_by_headings.pop(0)
            self.assertEqual('case_id', id_row['Source Field'])
            self.assertEqual('id', id_row['Field'])
            main_table = self.export_instance.selected_tables[0]
            self.assertEqual(len(main_table.selected_columns), len(data_by_headings))
            for i, input_column in enumerate(main_table.selected_columns):
                self.assertEqual(input_column.label, data_by_headings[i]['Field'])
                self.assertEqual(_transform_path_for_case_properties(input_column.item.readable_path),
                                 data_by_headings[i]['Source Field'])

            # note: subtables not supported


class TestDETFormInstance(SimpleTestCase, TestFileMixin):
    file_path = ['data', 'det']
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.export_instance = FormExportInstance.wrap(cls.get_json('form_export_instance'))

    def test_empty(self):
        old_tables = self.export_instance.tables
        self.export_instance.tables = []
        with self.assertRaises(DETConfigError):
            generate_from_form_export_instance(self.export_instance, BytesIO())
        self.export_instance.tables = old_tables

    def test_generate_from_form_schema(self):
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx') as tmp:
            generate_from_form_export_instance(self.export_instance, tmp)
            wb = load_workbook(filename=tmp.name)
            ws = wb.worksheets[0]
            all_data = list(ws.values)
            headings = all_data.pop(0)
            data_by_headings = [dict(zip(headings, row)) for row in all_data]
            id_row = data_by_headings.pop(0)
            self.assertEqual('form.meta.instanceID', id_row['Source Field'])
            self.assertEqual('id', id_row['Field'])
            main_table = self.export_instance.selected_tables[0]
            self.assertEqual(len(main_table.selected_columns), len(data_by_headings))
            # basic sanity check
            for i, input_column in enumerate(main_table.selected_columns):
                self.assertEqual(input_column.label, data_by_headings[i]['Field'])
                self.assertEqual(input_column.item.readable_path, data_by_headings[i]['Source Field'])

            # test individual fields / types
            data_by_headings_by_source_field = {
                row['Source Field']: row for row in data_by_headings
            }
            self.assertEqual('str2date', data_by_headings_by_source_field['received_on']['Map Via'])
            self.assertEqual('str2date', data_by_headings_by_source_field['form.event_date']['Map Via'])
            self.assertEqual('str2num', data_by_headings_by_source_field['form.event_duration_minutes']['Map Via'])


class TestDETFormInstanceWithRepeat(SimpleTestCase, TestFileMixin):
    file_path = ['data', 'det']
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.export_instance = FormExportInstance.wrap(cls.get_json('form_export_instance_with_repeat'))

    def test_main_table_not_selected(self):
        self.export_instance.tables[0].selected = False
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx') as tmp:
            generate_from_form_export_instance(self.export_instance, tmp)
            wb = load_workbook(filename=tmp.name)
            self.assertEqual(1, len(wb.worksheets))
            repeat_ws = wb.worksheets[0]
            self._check_repeat_worksheet(repeat_ws)

        # restore self.export_instance changes made in this test
        self.export_instance.tables[0].selected = True

    def test_generate_from_form_schema(self):
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx') as tmp:
            generate_from_form_export_instance(self.export_instance, tmp)
            wb = load_workbook(filename=tmp.name)
            repeat_ws = wb.worksheets[1]
            self._check_repeat_worksheet(repeat_ws)

    def _check_repeat_worksheet(self, repeat_ws):
        repeat_data = list(repeat_ws.values)
        headings = repeat_data.pop(0)
        rows_by_headings = [dict(zip(headings, row)) for row in repeat_data]
        self.assertEqual('form.form.children[*]', rows_by_headings[0]['Data Source'])
        self.assertEqual('child_name', rows_by_headings[1]['Source Field'])
        self.assertEqual('child_dob', rows_by_headings[2]['Source Field'])
