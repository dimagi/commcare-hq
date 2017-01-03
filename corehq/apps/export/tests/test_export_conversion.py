import os
from collections import namedtuple
import mock

from django.test import TestCase, SimpleTestCase

from dimagi.utils.couch.undo import DELETED_SUFFIX
from couchexport.models import SavedExportSchema
from toggle.shortcuts import toggle_enabled, clear_toggle_cache, set_toggle

from corehq.toggles import OLD_EXPORTS, NAMESPACE_DOMAIN
from corehq.util.test_utils import TestFileMixin, generate_cases
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.export.models import (
    FormExportDataSchema,
    CaseExportDataSchema,
    ExportGroupSchema,
    UserDefinedExportColumn,
    ExportItem,
    StockItem,
    LabelItem,
    FormExportInstance,
    CaseExportInstance,
    MAIN_TABLE,
    PARENT_CASE_TABLE,
    PathNode,
    CASE_HISTORY_TABLE,
    SplitGPSExportColumn,
)
from corehq.apps.reports.models import HQGroupExportConfiguration
from corehq.apps.app_manager.models import Domain, Application, RemoteApp, Module
from corehq.apps.export.utils import (
    convert_saved_export_to_export_instance,
    _convert_index_to_path_nodes,
    revert_new_exports,
    _is_remote_app_conversion,
    _is_form_stock_question,
    migrate_domain,
)
from corehq.apps.export.const import (
    DEID_ID_TRANSFORM,
    DEID_DATE_TRANSFORM,
    CASE_NAME_TRANSFORM,
    FORM_EXPORT,
    CASE_EXPORT,
)
from corehq.apps.export.dbaccessors import (
    delete_all_export_instances,
    delete_all_inferred_schemas,
)

MockRequest = namedtuple('MockRequest', 'domain')


@mock.patch(
    'corehq.apps.export.utils.stale_get_export_count',
    return_value=0,
)
class TestMigrateDomain(TestCase):
    """
    This tests some specifics of migrate_domain that do not have to do with
    the actual conversion process. That is tested in another test class
    """
    domain = 'test-migrate-domain'

    def setUp(self):
        self.project = Domain(name=self.domain)
        self.project.save()
        clear_toggle_cache(OLD_EXPORTS.slug, self.domain, namespace=NAMESPACE_DOMAIN)
        set_toggle(OLD_EXPORTS.slug, self.domain, True, namespace=NAMESPACE_DOMAIN)

    def tearDown(self):
        self.project.delete()

    def test_toggle_turned_on(self, _):
        self.assertTrue(toggle_enabled(OLD_EXPORTS.slug, self.domain, namespace=NAMESPACE_DOMAIN))
        migrate_domain(self.domain)
        self.assertFalse(toggle_enabled(OLD_EXPORTS.slug, self.domain, namespace=NAMESPACE_DOMAIN))


class TestIsFormStockExportQuestion(SimpleTestCase):
    """Ensures that we can guess that a column is a stock question"""


@generate_cases([
    ('form.balance.entry.@id', True),
    ('form.balance.entry.@notme', False),
    ('form.balance.@date', True),
    ('form.balance.@notme', False),

    ('form.transfer.entry.@id', True),
    ('form.transfer.entry.@notme', False),
    ('form.transfer.@date', True),
    ('form.transfer.@notme', False),

    ('form.notme.@quantity', False),
    ('tooshort', False),
    ('tooshort.tooshort', False),
    ('', False),
], TestIsFormStockExportQuestion)
def test_is_form_stock_question(self, index, expected):
    self.assertEqual(_is_form_stock_question(index), expected)


class TestIsRemoteAppConversion(TestCase):
    domain = 'test-is-remote-app'

    @classmethod
    def setUpClass(cls):
        cls.project = Domain(name=cls.domain)
        cls.project.save()

        cls.apps = [
            # .wrap adds lots of stuff in, but is hard to call directly
            # this workaround seems to work
            Application.wrap(
                Application(
                    domain=cls.domain,
                    name='foo',
                    version=1,
                    modules=[Module()]
                ).to_json()
            ),
            RemoteApp.wrap(RemoteApp(domain=cls.domain, version=1, name='bar').to_json()),
        ]
        for app in cls.apps:
            app.save()

    @classmethod
    def tearDownClass(cls):
        for app in cls.apps:
            app.delete()
        cls.project.delete()

    def test_form_remote_app_conversion(self):
        self.assertFalse(_is_remote_app_conversion(self.domain, self.apps[0]._id, FORM_EXPORT))
        self.assertTrue(_is_remote_app_conversion(self.domain, self.apps[1]._id, FORM_EXPORT))

    def test_case_remote_app_conversion(self):
        self.assertTrue(_is_remote_app_conversion(self.domain, None, CASE_EXPORT))
        self.assertFalse(_is_remote_app_conversion('wrong-domain', None, CASE_EXPORT))


class TestConvertBase(TestCase, TestFileMixin):
    file_path = ('data', 'saved_export_schemas')
    root = os.path.dirname(__file__)
    app_id = '58b0156dc3a8420669efb286bc81e048'
    domain = 'convert-domain'

    def setUp(self):
        super(TestConvertBase, self).setUp()
        delete_all_export_instances()

    def tearDown(self):
        delete_all_inferred_schemas()

    def _convert_form_export(self, export_file_name, force=False):
        return self._convert_export(
            'corehq.apps.export.models.new.FormExportDataSchema.generate_schema_from_builds',
            export_file_name,
            force=force
        )

    def _convert_case_export(self, export_file_name, force=False):
        return self._convert_export(
            'corehq.apps.export.models.new.CaseExportDataSchema.generate_schema_from_builds',
            export_file_name,
            force=force
        )

    def _convert_export(self, mock_path, export_file_name, force=False):
        saved_export_schema = SavedExportSchema.wrap(self.get_json(export_file_name))

        with mock.patch.object(SavedExportSchema, 'save', return_value='False Save'):
            with mock.patch(
                    mock_path,
                    return_value=self.schema):
                instance, meta = convert_saved_export_to_export_instance(
                    self.domain,
                    saved_export_schema,
                    force_convert_columns=force,
                )

        return instance, meta


@mock.patch(
    'corehq.apps.export.models.new.get_request',
    return_value=MockRequest(domain='my-domain'),
)
class TestForceConvertExport(TestConvertBase):

    @classmethod
    def setUpClass(cls):
        super(TestForceConvertExport, cls).setUpClass()
        cls.project = create_domain(cls.domain)
        cls.project.commtrack_enabled = True
        cls.project.save()
        cls.schema = CaseExportDataSchema(
            domain=cls.domain,
            case_type='wonderwoman',
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=[PathNode(name='DOB')],
                            label='Case Property DOB',
                            last_occurrences={cls.app_id: 3},
                        ),
                    ],
                    last_occurrences={cls.app_id: 3},
                ),
            ],
        )

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestForceConvertExport, cls).tearDownClass()

    def test_force_column_convert(self, _):
        instance, _ = self._convert_case_export('case')
        table = instance.get_table(MAIN_TABLE)

        index, column = table.get_column([PathNode(name='DOB')], 'ExportItem', None)
        self.assertIsNotNone(column)
        index, column = table.get_column([PathNode(name='age')], 'ExportItem', None)
        # When we don't force the convert we shouldn't convert when it's not in the schema
        self.assertIsNone(column)

        instance, _ = self._convert_case_export('case', force=True)
        table = instance.get_table(MAIN_TABLE)

        index, column = table.get_column([PathNode(name='age')], 'ScalarItem', None)
        # When we do force the convert we should convert even when it's not in the schema
        self.assertIsNotNone(column)
        self.assertEqual(column.label, 'Age Label')
        self.assertTrue(column.item.inferred)
        self.assertEqual(column.deid_transform, DEID_ID_TRANSFORM)

        index_dob, _ = table.get_column([PathNode(name='DOB')], 'ExportItem', None)

        # Ensure that the ordering remains correct with forced column conversion
        self.assertTrue(index > index_dob)


@mock.patch(
    'corehq.apps.export.models.new.get_request',
    return_value=MockRequest(domain='my-domain'),
)
class TestConvertSavedExportSchemaToCaseExportInstance(TestConvertBase):

    @classmethod
    def setUpClass(cls):
        super(TestConvertSavedExportSchemaToCaseExportInstance, cls).setUpClass()
        cls.project = create_domain(cls.domain)
        cls.project.commtrack_enabled = True
        cls.project.save()
        cls.schema = CaseExportDataSchema(
            domain=cls.domain,
            case_type='wonderwoman',
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

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestConvertSavedExportSchemaToCaseExportInstance, cls).tearDownClass()

    def setUp(self):
        super(TestConvertSavedExportSchemaToCaseExportInstance, self).setUp()
        delete_all_export_instances()

    def test_basic_conversion(self, _):
        instance, _ = self._convert_case_export('case')

        self.assertEqual(instance.transform_dates, True)
        self.assertEqual(instance.name, 'Case Example')
        self.assertEqual(instance.export_format, 'csv')
        self.assertEqual(instance.is_deidentified, False)
        self.assertEqual(instance.is_daily_saved_export, False)

        table = instance.get_table(MAIN_TABLE)
        self.assertEqual(table.label, 'Cases')
        self.assertTrue(table.selected)

        index, column = table.get_column([PathNode(name='DOB')], 'ExportItem', None)
        self.assertEqual(column.label, 'DOB Saved')
        self.assertEqual(column.selected, True)

    def test_daily_saved_conversion(self, _):
        # ID is from corehq/apps/export/tests/data/saved_export_schemas/case.json
        self.group_config = HQGroupExportConfiguration.add_custom_export(
            self.domain,
            '92e5f9a6624a637c2080957475cd446d'
        )
        self.group_config.save()
        self.addCleanup(self.group_config.delete)

        instance, _ = self._convert_case_export('case')

        self.assertEqual(instance.transform_dates, True)
        self.assertEqual(instance.name, 'Case Example')
        self.assertEqual(instance.export_format, 'csv')
        self.assertEqual(instance.is_deidentified, False)
        self.assertEqual(instance.is_daily_saved_export, True)

        table = instance.get_table(MAIN_TABLE)
        self.assertEqual(table.label, 'Cases')
        self.assertTrue(table.selected)

        index, column = table.get_column([PathNode(name='DOB')], 'ExportItem', None)
        self.assertEqual(column.label, 'DOB Saved')
        self.assertEqual(column.selected, True)

    def test_parent_case_conversion(self, _):
        instance, _ = self._convert_case_export('parent_case')

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
        instance, _ = self._convert_case_export('case_history')

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
        instance, _ = self._convert_case_export('stock')
        table = instance.get_table(MAIN_TABLE)
        path = [PathNode(name='stock')]
        index, column = table.get_column(path, 'ExportItem', None)
        self.assertTrue(column.selected)

    @mock.patch(
        'corehq.apps.export.utils._is_remote_app_conversion',
        return_value=True,
    )
    def test_remote_app_conversion(self, _, __):
        instance, meta = self._convert_case_export('remote_app')
        table = instance.get_table(MAIN_TABLE)
        index, column = table.get_column(
            [PathNode(name='age')],
            'ScalarItem',
            None,
        )
        self.assertIsNotNone(column)
        self.assertEqual(column.label, 'age')
        self.assertTrue(meta.is_remote_app_migration)


@mock.patch(
    'corehq.apps.export.models.new.get_request',
    return_value=MockRequest(domain='convert-domain'),
)
@mock.patch(
    'corehq.apps.export.utils._is_remote_app_conversion',
    return_value=False,
)
class TestConvertSavedExportSchemaToFormExportInstance(TestConvertBase):

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
                        LabelItem(
                            path=[PathNode(name='form'), PathNode(name='label')],
                            label='label',
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

    def test_basic_conversion(self, _, __):
        instance, _ = self._convert_form_export('basic')

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

    def test_label_conversion(self, _, __):
        instance, _ = self._convert_form_export('basic_label')

        table = instance.get_table(MAIN_TABLE)
        index, column = table.get_column(
            [PathNode(name='form'), PathNode(name='label')],
            'LabelItem',
            None,
        )
        self.assertEqual(column.label, 'My Label')
        self.assertEqual(column.selected, True)

    def test_conversion_with_text_nodes(self, _, __):
        instance, _ = self._convert_form_export('basic_with_text_nodes')

        table = instance.get_table(MAIN_TABLE)

        index, column = table.get_column(
            [PathNode(name='form'), PathNode(name='meta'), PathNode(name='location')],
            'GeopointItem',
            None,
        )
        self.assertEqual(column.label, 'Meta Location')
        self.assertEqual(column.selected, True)
        self.assertTrue(isinstance(column, SplitGPSExportColumn))

    def test_repeat_conversion(self, _, __):
        instance, _ = self._convert_form_export('repeat')

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

    def test_nested_repeat_conversion(self, _, __):
        instance, _ = self._convert_form_export('repeat_nested')

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

    def test_transform_conversion(self, _, __):
        instance, _ = self._convert_form_export('deid_transforms')

        table = instance.get_table(MAIN_TABLE)

        index, column = table.get_column(
            [PathNode(name='form'), PathNode(name='deid_id')], 'ExportItem', None
        )
        self.assertEqual(column.deid_transform, DEID_ID_TRANSFORM)

        index, column = table.get_column(
            [PathNode(name='form'), PathNode(name='deid_date')], 'ExportItem', None
        )
        self.assertEqual(column.deid_transform, DEID_DATE_TRANSFORM)

    def test_skippable_export_columns(self, _, __):
        instance, _ = self._convert_form_export('skippable_properties')

        table = instance.get_table(MAIN_TABLE)

        index, column = table.get_column(
            [PathNode(name='initial_processing_complete')], None, None
        )
        self.assertIsInstance(column, UserDefinedExportColumn)
        self.assertFalse(column.is_editable)
        self.assertEqual(column.custom_path, [PathNode(name='initial_processing_complete')])

    def test_system_property_conversion(self, _, __):
        instance, _ = self._convert_form_export('system_properties')

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

    def test_remote_app_conversion_with_repeats(self, _, __):
        with mock.patch('corehq.apps.export.utils._is_remote_app_conversion', return_value=True):
            instance, meta = self._convert_form_export('remote_app_repeats')

        table = instance.get_table([PathNode(name='form'), PathNode(name='custom_repeat', is_repeat=True)])

        self.assertTrue(table.is_user_defined)

        index, column = table.get_column(
            [
                PathNode(name='form'),
                PathNode(name='custom_repeat', is_repeat=True),
                PathNode(name='DOB'),
            ],
            None,
            None,
        )
        self.assertIsNotNone(column)
        self.assertEqual(column.label, 'DOB Saved')
        self.assertTrue(meta.is_remote_app_migration)


@mock.patch(
    'corehq.apps.export.models.new.get_request',
    return_value=MockRequest(domain='convert-domain'),
)
@mock.patch(
    'corehq.apps.export.utils._is_remote_app_conversion',
    return_value=False,
)
class TestConversionOrdering(TestConvertBase):

    @classmethod
    def setUpClass(cls):
        super(TestConversionOrdering, cls).setUpClass()
        cls.schema = FormExportDataSchema(
            domain=cls.domain,
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=[PathNode(name='form'), PathNode(name='question1')],
                            label='q1',
                        ),
                        ExportItem(
                            path=[PathNode(name='form'), PathNode(name='question2')],
                            label='q2',
                        ),
                        ExportItem(
                            path=[PathNode(name='form'), PathNode(name='other')],
                            label='other',
                        ),
                        ExportItem(
                            path=[PathNode(name='form'), PathNode(name='question3')],
                            label='q3',
                        ),
                    ],
                    last_occurrences={cls.app_id: 2},
                ),
            ]
        )

    def test_conversion_ordering(self, _, __):
        instance, _ = self._convert_form_export('conversion_ordering')

        table = instance.get_table(MAIN_TABLE)
        column = table.columns[0]
        self.assertEqual(
            column.item.path,
            [PathNode(name='form'), PathNode(name='question3')],
        )

        column = table.columns[1]
        self.assertEqual(
            column.item.path,
            [PathNode(name='form'), PathNode(name='question2')],
        )

        column = table.columns[2]
        self.assertEqual(
            column.item.path,
            [PathNode(name='form'), PathNode(name='question1')],
        )

        self.assertIn(column, table.columns)


@mock.patch(
    'corehq.apps.export.models.new.get_request',
    return_value=MockRequest(domain='convert-domain'),
)
@mock.patch(
    'corehq.apps.export.utils._is_remote_app_conversion',
    return_value=False,
)
class TestSingleNodeRepeatConversion(TestConvertBase):

    @classmethod
    def setUpClass(cls):
        super(TestSingleNodeRepeatConversion, cls).setUpClass()
        cls.schema = FormExportDataSchema(
            domain=cls.domain,
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[],
                    last_occurrences={cls.app_id: 2},
                ),
                ExportGroupSchema(
                    path=[PathNode(name='form'), PathNode(name='repeat', is_repeat=True)],
                    items=[
                        ExportItem(
                            path=[
                                PathNode(name='form'),
                                PathNode(name='repeat', is_repeat=True),
                                PathNode(name='single_answer')
                            ],
                            label='Single Answer',
                            last_occurrences={cls.app_id: 2},
                        )
                    ],
                    last_occurrences={cls.app_id: 2},
                ),
            ]
        )

    def test_single_node_repeats(self, _, __):
        """
        This test ensures that if a repeat only receives one entry, that the selection
        will still be migrated.
        """
        instance, _ = self._convert_form_export('single_node_repeat')

        table = instance.get_table([PathNode(name='form'), PathNode(name='repeat', is_repeat=True)])
        index, column = table.get_column(
            [
                PathNode(name='form'),
                PathNode(name='repeat', is_repeat=True),
                PathNode(name='single_answer'),
            ],
            'ExportItem',
            None
        )
        self.assertTrue(column.selected)


@mock.patch(
    'corehq.apps.export.models.new.get_request',
    return_value=MockRequest(domain='convert-domain'),
)
@mock.patch(
    'corehq.apps.export.utils._is_remote_app_conversion',
    return_value=False,
)
class TestConvertStockFormExport(TestConvertBase):

    @classmethod
    def setUpClass(cls):
        super(TestConvertStockFormExport, cls).setUpClass()
        cls.schema = FormExportDataSchema(
            domain=cls.domain,
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        StockItem(
                            path=[
                                PathNode(name='form'),
                                PathNode(name='transfer:questionid'),
                                PathNode(name='entry'),
                                PathNode(name='@id'),
                            ],
                            label='Question 1',
                            last_occurrences={cls.app_id: 3},
                        ),
                    ],
                    last_occurrences={cls.app_id: 2},
                ),
                ExportGroupSchema(
                    path=[PathNode(name='form'), PathNode(name='repeat', is_repeat=True)],
                    items=[
                        StockItem(
                            path=[
                                PathNode(name='form'),
                                PathNode(name='repeat', is_repeat=True),
                                PathNode(name='transfer:questionid'),
                                PathNode(name='entry'),
                                PathNode(name='@id'),
                            ],
                            label='Question 1',
                            last_occurrences={cls.app_id: 3},
                        ),
                    ],
                    last_occurrences={cls.app_id: 2},
                ),
            ]
        )

    def test_convert_form_export_stock_basic(self, _, __):
        instance, _ = self._convert_form_export('stock_form_export')

        table = instance.get_table(MAIN_TABLE)
        index, column = table.get_column(
            [
                PathNode(name='form'),
                PathNode(name='transfer:questionid'),
                PathNode(name='entry'),
                PathNode(name='@id'),
            ],
            'StockItem',
            None,
        )
        self.assertTrue(column.selected)

    def test_convert_form_export_stock_in_repeat(self, _, __):
        instance, _ = self._convert_form_export('stock_form_export_repeat')
        table = instance.get_table([PathNode(name='form'), PathNode(name='repeat', is_repeat=True)])
        index, column = table.get_column(
            [
                PathNode(name='form'),
                PathNode(name='repeat', is_repeat=True),
                PathNode(name='transfer:questionid'),
                PathNode(name='entry'),
                PathNode(name='@id'),
            ],
            'StockItem',
            None,
        )
        self.assertTrue(column.selected)


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
