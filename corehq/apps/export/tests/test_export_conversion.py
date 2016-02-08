import os
import mock

from django.test import TestCase, SimpleTestCase

from couchexport.models import SavedExportSchema

from corehq.util.test_utils import TestFileMixin, generate_cases
from corehq.apps.export.models import (
    FormExportInstance,
    FormExportDataSchema,
    ExportGroupSchema,
    ExportItem,
)
from corehq.apps.export.utils import convert_saved_export_to_export_instance, _convert_index_to_path
from corehq.apps.export.const import MAIN_TABLE


class TestConvertSavedExportSchemaToFormExportInstance(TestCase, TestFileMixin):
    file_path = ('data', 'saved_export_schemas')
    root = os.path.dirname(__file__)
    app_id = '58b0156dc3a8420669efb286bc81e048'

    @classmethod
    def setUpClass(cls):
        cls.schema = FormExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=['data', 'question1'],
                            label='Question 1',
                            last_occurrences={cls.app_id: 3},
                        )
                    ],
                    last_occurrences={cls.app_id: 3},
                ),
                ExportGroupSchema(
                    path=['data', 'repeat'],
                    items=[
                        ExportItem(
                            path=['data', 'repeat', 'question2'],
                            label='Question 2',
                            last_occurrences={cls.app_id: 2},
                        )
                    ],
                    last_occurrences={cls.app_id: 2},
                ),
            ],
        )

    def test_basic_conversion(self):

        saved_export_schema = SavedExportSchema.wrap(self.get_json('basic'))
        with mock.patch(
                'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(saved_export_schema)

        self.assertEqual(instance.split_multiselects, False)
        self.assertEqual(instance.transform_dates, True)
        self.assertEqual(instance.name, 'Tester')
        self.assertEqual(instance.export_format, 'csv')
        self.assertEqual(instance.is_deidentified, False)
        self.assertEqual(instance.include_errors, False)

        table = instance.get_table(MAIN_TABLE)
        self.assertEqual(table.display_name, 'My Forms')

        column = table.get_column(['data', 'question1'])
        self.assertEqual(column.label, 'Question One')
        self.assertEqual(column.selected, True)

    def test_repeat_conversion(self):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('repeat'))
        with mock.patch(
                'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(saved_export_schema)

        self.assertEqual(instance.name, 'Repeat Tester')
        table = instance.get_table(['data', 'repeat'])
        self.assertEqual(table.display_name, 'Repeat: question1')

        column = table.get_column(['data', 'repeat', 'question2'])
        self.assertEqual(column.label, 'Question Two')
        self.assertEqual(column.selected, True)


class TestConvertIndexToPath(SimpleTestCase):
    """Test the conversion of old style index to new style path"""


@generate_cases([
    ('form.question1', ['data', 'question1']),
    ('#', MAIN_TABLE),
    ('#.form.question1.#', ['data', 'question1']),  # Repeat group
], TestConvertIndexToPath)
def test_convert_index_to_path(self, index, path):
    self.assertEqual(_convert_index_to_path(index), path)
