import os
from collections import namedtuple
import mock

from django.test import TestCase, SimpleTestCase

from dimagi.utils.couch.undo import DELETED_SUFFIX
from couchexport.models import SavedExportSchema

from corehq.util.test_utils import TestFileMixin, generate_cases
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.export.models import (
    FormExportDataSchema,
    CaseExportDataSchema,
    ExportGroupSchema,
    ExportItem,
    FormExportInstance,
    CaseExportInstance,
)
from corehq.apps.export.utils import (
    convert_saved_export_to_export_instance,
    _convert_index_to_path_nodes,
    revert_new_exports,
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

MockRequest = namedtuple('MockRequest', 'domain')


@mock.patch(
    'corehq.apps.export.models.new.get_request',
    return_value=MockRequest(domain='my-domain'),
)
class TestConvertSavedExportSchemaToCaseExportInstance(TestCase, TestFileMixin):
    file_path = ('data', 'saved_export_schemas')
    root = os.path.dirname(__file__)
    app_id = '58b0156dc3a8420669efb286bc81e048'
    domain = 'convert-domain'

    @classmethod
    def setUpClass(cls):
        super(TestConvertSavedExportSchemaToCaseExportInstance, cls).setUpClass()
        cls.project = create_domain(cls.domain)
        cls.project.commtrack_enabled = True
        cls.project.save()
        cls.schema = CaseExportDataSchema(
            domain=cls.domain,
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

    def test_basic_conversion(self, _):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('case'))
        with mock.patch(
                'corehq.apps.export.models.new.CaseExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(self.domain, saved_export_schema)

        self.assertEqual(instance.transform_dates, True)
        self.assertEqual(instance.name, 'Case Example')
        self.assertEqual(instance.export_format, 'csv')
        self.assertEqual(instance.is_deidentified, False)

        table = instance.get_table(MAIN_TABLE)
        self.assertEqual(table.label, 'Cases')
        self.assertTrue(table.selected)

        index, column = table.get_column([PathNode(name='DOB')], 'ExportItem', None)
        self.assertEqual(column.label, 'DOB Saved')
        self.assertEqual(column.selected, True)

    def test_parent_case_conversion(self, _):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('parent_case'))
        with mock.patch(
                'corehq.apps.export.models.new.CaseExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(self.domain, saved_export_schema)

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
            index, column = table.get_column(path, 'ExportItem', None)
            self.assertEqual(column.selected, selected, '{} selected is not {}'.format(path, selected))

    def test_case_history_conversion(self, _):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('case_history'))
        with mock.patch(
                'corehq.apps.export.models.new.CaseExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(self.domain, saved_export_schema)

        table = instance.get_table(CASE_HISTORY_TABLE)
        self.assertEqual(table.label, 'Case History')

        expected_paths = [
            ([PathNode(name='actions', is_repeat=True), PathNode(name='action_type')], True),
            ([PathNode(name='number')], True),
            ([PathNode(name='actions', is_repeat=True), PathNode(name='server_date')], True),
            ([PathNode(name='actions', is_repeat=True), PathNode(name='xform_name')], True),
        ]

        for path, selected in expected_paths:
            index, column = table.get_column(path, 'ExportItem', None)
            self.assertEqual(column.selected, selected, '{} selected is not {}'.format(path, selected))

    def test_stock_conversion(self, _):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('stock'))
        with mock.patch(
                'corehq.apps.export.models.new.CaseExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(self.domain, saved_export_schema)
        table = instance.get_table(MAIN_TABLE)
        path = [PathNode(name='stock')]
        index, column = table.get_column(path, 'ExportItem', None)
        self.assertTrue(column.selected)


@mock.patch(
    'corehq.apps.export.models.new.get_request',
    return_value=MockRequest(domain='my-domain'),
)
class TestConvertSavedExportSchemaToFormExportInstance(TestCase, TestFileMixin):
    file_path = ('data', 'saved_export_schemas')
    root = os.path.dirname(__file__)
    app_id = '58b0156dc3a8420669efb286bc81e048'
    domain = 'convert-domain'

    @classmethod
    def setUpClass(cls):
        super(TestConvertSavedExportSchemaToFormExportInstance, cls).setUpClass()
        cls.schema = FormExportDataSchema(
            domain=cls.domain,
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

    def test_basic_conversion(self, _):

        saved_export_schema = SavedExportSchema.wrap(self.get_json('basic'))
        with mock.patch(
                'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(self.domain, saved_export_schema)

        self.assertEqual(instance.split_multiselects, False)
        self.assertEqual(instance.transform_dates, True)
        self.assertEqual(instance.name, 'Tester')
        self.assertEqual(instance.export_format, 'csv')
        self.assertEqual(instance.is_deidentified, False)
        self.assertEqual(instance.include_errors, False)

        table = instance.get_table(MAIN_TABLE)
        self.assertEqual(table.label, 'My Forms')

        index, column = table.get_column(
            [PathNode(name='form'), PathNode(name='question1')],
            'ExportItem',
            None,
        )
        self.assertEqual(column.label, 'Question One')
        self.assertEqual(column.selected, True)

    def test_repeat_conversion(self, _):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('repeat'))
        with mock.patch(
                'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(self.domain, saved_export_schema)

        self.assertEqual(instance.name, 'Repeat Tester')
        table = instance.get_table([PathNode(name='form'), PathNode(name='repeat', is_repeat=True)])
        self.assertEqual(table.label, 'Repeat: question1')
        self.assertTrue(table.selected)

        index, column = table.get_column(
            [PathNode(name='form'),
             PathNode(name='repeat', is_repeat=True),
             PathNode(name='question2')],
            'ExportItem',
            None
        )
        self.assertEqual(column.label, 'Question Two')
        self.assertEqual(column.selected, True)

        index, column = table.get_column(
            [PathNode(name='number')],
            'ExportItem',
            None
        )
        self.assertEqual(column.selected, True)

    def test_nested_repeat_conversion(self, _):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('repeat_nested'))
        with mock.patch(
                'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(self.domain, saved_export_schema)

        self.assertEqual(instance.name, 'Nested Repeat')

        # Check for first repeat table
        table = instance.get_table([PathNode(name='form'), PathNode(name='repeat', is_repeat=True)])
        self.assertTrue(table.selected)
        self.assertEqual(table.label, 'Repeat: One')

        index, column = table.get_column(
            [PathNode(name='form'),
             PathNode(name='repeat', is_repeat=True),
             PathNode(name='question2')],
            'ExportItem',
            None
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

        index, column = table.get_column(
            [PathNode(name='form'),
             PathNode(name='repeat', is_repeat=True),
             PathNode(name='repeat_nested', is_repeat=True),
             PathNode(name='nested')],
            'ExportItem',
            None,
        )
        self.assertEqual(column.label, 'Modified Nested')
        self.assertEqual(column.selected, True)

    def test_transform_conversion(self, _):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('deid_transforms'))
        with mock.patch(
                'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(self.domain, saved_export_schema)

        table = instance.get_table(MAIN_TABLE)

        index, column = table.get_column(
            [PathNode(name='form'), PathNode(name='deid_id')], 'ExportItem', None
        )
        self.assertEqual(column.deid_transform, DEID_ID_TRANSFORM)

        index, column = table.get_column(
            [PathNode(name='form'), PathNode(name='deid_date')], 'ExportItem', None
        )
        self.assertEqual(column.deid_transform, DEID_DATE_TRANSFORM)

    def test_system_property_conversion(self, _):
        saved_export_schema = SavedExportSchema.wrap(self.get_json('system_properties'))
        with mock.patch(
                'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
                return_value=self.schema):
            instance = convert_saved_export_to_export_instance(self.domain, saved_export_schema)

        self.assertEqual(instance.name, 'System Properties')

        # Check for first repeat table
        table = instance.get_table(MAIN_TABLE)
        self.assertEqual(table.label, 'Forms')

        expected_paths = [
            ([PathNode(name='xmlns')], None, True),
            ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='userID')], None, True),
            ([PathNode(name='form'), PathNode(name='case'), PathNode(name='@case_id')], None, True),
            (
                [PathNode(name='form'), PathNode(name='case'), PathNode(name='@case_id')],
                CASE_NAME_TRANSFORM,
                True
            ),
        ]
        for path, transform, selected in expected_paths:
            index, column = table.get_column(path, 'ExportItem', transform)
            self.assertEqual(column.selected, selected, '{} selected is not {}'.format(path, selected))


class TestRevertNewExports(TestCase):

    def setUp(cls):
        cls.new_exports = [
            FormExportInstance(),
            CaseExportInstance(),
        ]
        for export in cls.new_exports:
            export.save()

    def tearDown(cls):
        for export in cls.new_exports:
            export.delete()

    def test_revert_new_exports(self):
        reverted = revert_new_exports(self.new_exports)
        self.assertListEqual(reverted, [])
        for export in self.new_exports:
            self.assertTrue(export.doc_type.endswith(DELETED_SUFFIX))

    def test_revert_new_exports_restore_old(self):
        saved_export_schema = SavedExportSchema(index=['my-domain', 'xmlns'])
        saved_export_schema.doc_type += DELETED_SUFFIX
        saved_export_schema.save()
        self.new_exports[0].legacy_saved_export_schema_id = saved_export_schema._id

        reverted = revert_new_exports(self.new_exports)
        self.assertEqual(len(reverted), 1)
        self.assertFalse(reverted[0].doc_type.endswith(DELETED_SUFFIX))
        saved_export_schema.delete()


class TestConvertIndexToPath(SimpleTestCase):
    """Test the conversion of old style index to new style path"""


@generate_cases([
    ('form.question1', [PathNode(name='form'), PathNode(name='question1')]),
    ('#', MAIN_TABLE),
    ('#.form.question1.#', [PathNode(name='form'), PathNode(name='question1', is_repeat=True)]),  # Repeat group
], TestConvertIndexToPath)
def test_convert_index_to_path_nodes(self, index, path):
    self.assertEqual(_convert_index_to_path_nodes(index), path)
