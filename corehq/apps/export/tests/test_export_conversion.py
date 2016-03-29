import os
import mock

from django.test import TestCase, SimpleTestCase

from couchexport.models import SavedExportSchema

from corehq.util.test_utils import TestFileMixin, generate_cases
from corehq.apps.export.models import (
    FormExportDataSchema,
    CaseExportDataSchema,
    ExportGroupSchema,
    ExportItem,
)
from corehq.apps.export.utils import (
    convert_saved_export_to_export_instance,
    _convert_index_to_path_nodes,
)
from corehq.apps.export.const import (
    DEID_ID_TRANSFORM,
    DEID_DATE_TRANSFORM,
    CASE_NAME_TRANSFORM,
)
from corehq.apps.export.models import (
    MAIN_TABLE,
    PARENT_CASE_TABLE,
    PathNode,
    CASE_HISTORY_TABLE,
)


class TestConvertSavedExportSchemaToCaseExportInstance(TestCase, TestFileMixin):
    file_path = ('data', 'saved_export_schemas')
    root = os.path.dirname(__file__)
    app_id = '58b0156dc3a8420669efb286bc81e048'

    @classmethod
    def setUpClass(cls):
        cls.schema = CaseExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=[PathNode(name='DOB')],
                            label='Case Propery DOB',
                            last_occurrences={cls.app_id: 3},
                        ),
                    ],
                    last_occurrences={cls.app_id: 3},
                ),
                ExportGroupSchema(
                    path=CASE_HISTORY_TABLE,
                    last_occurrences={cls.app_id: 3},
                ),
                ExportGroupSchema(
                    path=PARENT_CASE_TABLE,
                    last_occurrences={cls.app_id: 3},
                ),
            ],
        )

    def test_basic_conversion(self):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('case'))
        with mock.patch(
                'corehq.apps.export.models.new.CaseExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(saved_export_schema)

        self.assertEqual(instance.transform_dates, True)
        self.assertEqual(instance.name, 'Case Example')
        self.assertEqual(instance.export_format, 'csv')
        self.assertEqual(instance.is_deidentified, False)

        table = instance.get_table(MAIN_TABLE)
        self.assertEqual(table.label, 'Cases')
        self.assertTrue(table.selected)

        column = table.get_column([PathNode(name='DOB')], [])
        self.assertEqual(column.label, 'DOB Saved')
        self.assertEqual(column.selected, True)

    def test_parent_case_conversion(self):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('parent_case'))
        with mock.patch(
                'corehq.apps.export.models.new.CaseExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(saved_export_schema)

        table = instance.get_table(PARENT_CASE_TABLE)
        self.assertEqual(table.label, 'Parent Cases')
        self.assertTrue(table.selected)

        expected_paths = [
            ([PathNode(name='indices', is_repeat=True), PathNode(name='referenced_id')], True),
            ([PathNode(name='indices', is_repeat=True), PathNode(name='referenced_type')], False),
            ([PathNode(name='indices', is_repeat=True), PathNode(name='relationship')], True),
            ([PathNode(name='indices', is_repeat=True), PathNode(name='doc_type')], True),
        ]

        for path, selected in expected_paths:
            column = table.get_column(path, [])
            self.assertEqual(column.selected, selected, '{} selected is not {}'.format(path, selected))

    def test_case_history_conversion(self):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('case_history'))
        with mock.patch(
                'corehq.apps.export.models.new.CaseExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(saved_export_schema)

        table = instance.get_table(CASE_HISTORY_TABLE)
        self.assertEqual(table.label, 'Case History')

        expected_paths = [
            ([PathNode(name='actions', is_repeat=True), PathNode(name='action_type')], True),
            ([PathNode(name='number')], True),
            ([PathNode(name='actions', is_repeat=True), PathNode(name='server_date')], True),
            ([PathNode(name='actions', is_repeat=True), PathNode(name='xform_name')], True),
        ]

        for path, selected in expected_paths:
            column = table.get_column(path, [])
            self.assertEqual(column.selected, selected, '{} selected is not {}'.format(path, selected))


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
                            path=[PathNode(name='form'), PathNode(name='question1')],
                            label='Question 1 Not updated',
                            last_occurrences={cls.app_id: 3},
                        ),
                        ExportItem(
                            path=[PathNode(name='form'), PathNode(name='deid_id')],
                            label='Question 1',
                            last_occurrences={cls.app_id: 3},
                        ),
                        ExportItem(
                            path=[PathNode(name='form'), PathNode(name='deid_date')],
                            label='Question 1',
                            last_occurrences={cls.app_id: 3},
                        ),
                    ],
                    last_occurrences={cls.app_id: 3},
                ),
                ExportGroupSchema(
                    path=[PathNode(name='form'), PathNode(name='repeat', is_repeat=True)],
                    items=[
                        ExportItem(
                            path=[
                                PathNode(name='form'),
                                PathNode(name='repeat', is_repeat=True),
                                PathNode(name='question2')
                            ],
                            label='Question 2',
                            last_occurrences={cls.app_id: 2},
                        )
                    ],
                    last_occurrences={cls.app_id: 2},
                ),
                ExportGroupSchema(
                    path=[
                        PathNode(name='form'),
                        PathNode(name='repeat', is_repeat=True),
                        PathNode(name='repeat_nested', is_repeat=True),
                    ],
                    items=[
                        ExportItem(
                            path=[
                                PathNode(name='form'),
                                PathNode(name='repeat', is_repeat=True),
                                PathNode(name='repeat_nested', is_repeat=True),
                                PathNode(name='nested'),
                            ],
                            label='Nested Repeat',
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
        self.assertEqual(table.label, 'My Forms')

        column = table.get_column([PathNode(name='form'), PathNode(name='question1')], [])
        self.assertEqual(column.label, 'Question One')
        self.assertEqual(column.selected, True)

    def test_repeat_conversion(self):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('repeat'))
        with mock.patch(
                'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(saved_export_schema)

        self.assertEqual(instance.name, 'Repeat Tester')
        table = instance.get_table([PathNode(name='form'), PathNode(name='repeat', is_repeat=True)])
        self.assertEqual(table.label, 'Repeat: question1')
        self.assertTrue(table.selected)

        column = table.get_column(
            [PathNode(name='form'),
             PathNode(name='repeat', is_repeat=True),
             PathNode(name='question2')],
            []
        )
        self.assertEqual(column.label, 'Question Two')
        self.assertEqual(column.selected, True)

        column = table.get_column(
            [PathNode(name='number')],
            []
        )
        self.assertEqual(column.selected, True)

    def test_nested_repeat_conversion(self):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('repeat_nested'))
        with mock.patch(
                'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(saved_export_schema)

        self.assertEqual(instance.name, 'Nested Repeat')

        # Check for first repeat table
        table = instance.get_table([PathNode(name='form'), PathNode(name='repeat', is_repeat=True)])
        self.assertTrue(table.selected)
        self.assertEqual(table.label, 'Repeat: One')

        column = table.get_column(
            [PathNode(name='form'),
             PathNode(name='repeat', is_repeat=True),
             PathNode(name='question2')],
            []
        )
        self.assertEqual(column.label, 'Modified Question Two')
        self.assertEqual(column.selected, True)

        # Check for second repeat table
        table = instance.get_table([
            PathNode(name='form'),
            PathNode(name='repeat', is_repeat=True),
            PathNode(name='repeat_nested', is_repeat=True)],
        )
        self.assertEqual(table.label, 'Repeat: One.#.Two')
        self.assertTrue(table.selected)

        column = table.get_column(
            [PathNode(name='form'),
             PathNode(name='repeat', is_repeat=True),
             PathNode(name='repeat_nested', is_repeat=True),
             PathNode(name='nested')],
            []
        )
        self.assertEqual(column.label, 'Modified Nested')
        self.assertEqual(column.selected, True)

    def test_transform_conversion(self):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('deid_transforms'))
        with mock.patch(
                'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(saved_export_schema)

        table = instance.get_table(MAIN_TABLE)

        column = table.get_column(
            [PathNode(name='form'), PathNode(name='deid_id')],
            []
        )
        self.assertEqual(column.transforms, [DEID_ID_TRANSFORM])

        column = table.get_column(
            [PathNode(name='form'), PathNode(name='deid_date')],
            []
        )
        self.assertEqual(column.transforms, [DEID_DATE_TRANSFORM])

    def test_system_property_conversion(self):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('system_properties'))
        with mock.patch(
                'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(saved_export_schema)

        self.assertEqual(instance.name, 'System Properties')

        # Check for first repeat table
        table = instance.get_table(MAIN_TABLE)
        self.assertEqual(table.label, 'Forms')

        expected_paths = [
            ([PathNode(name='xmlns')], [], True),
            ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='userID')], [], True),
            ([PathNode(name='form'), PathNode(name='case'), PathNode(name='@case_id')], [], True),
            (
                [PathNode(name='form'), PathNode(name='case'), PathNode(name='@case_id')],
                [CASE_NAME_TRANSFORM],
                True
            ),
        ]
        for path, transforms, selected in expected_paths:
            column = table.get_column(path, transforms)
            self.assertEqual(column.selected, selected, '{} selected is not {}'.format(path, selected))


class TestConvertIndexToPath(SimpleTestCase):
    """Test the conversion of old style index to new style path"""


@generate_cases([
    ('form.question1', [PathNode(name='form'), PathNode(name='question1')]),
    ('#', MAIN_TABLE),
    ('#.form.question1.#', [PathNode(name='form'), PathNode(name='question1', is_repeat=True)]),  # Repeat group
], TestConvertIndexToPath)
def test_convert_index_to_path_nodes(self, index, path):
    self.assertEqual(_convert_index_to_path_nodes(index), path)
