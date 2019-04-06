from __future__ import absolute_import
from __future__ import unicode_literals
import mock
from collections import namedtuple
from django.test import TestCase, SimpleTestCase

from corehq.apps.export.const import PROPERTY_TAG_CASE
from corehq.apps.domain.models import Domain
from corehq.apps.export.models import (
    ExportItem,
    StockItem,
    MultipleChoiceItem,
    FormExportDataSchema,
    CaseExportDataSchema,
    InferredSchema,
    InferredExportGroupSchema,
    ExportGroupSchema,
    CaseExportInstance,
    FormExportInstance,
    TableConfiguration,
    SplitExportColumn,
    StockFormExportColumn,
    PathNode,
    MAIN_TABLE,
    FormExportInstanceDefaults,
    MultiMediaExportColumn,
    ScalarItem,
)
from corehq.apps.export.system_properties import MAIN_FORM_TABLE_PROPERTIES, \
    TOP_MAIN_FORM_TABLE_PROPERTIES

MockRequest = namedtuple('MockRequest', 'domain')


@mock.patch(
    'corehq.apps.export.models.new.FormExportInstanceDefaults.get_default_instance_name',
    return_value='dummy-name'
)
@mock.patch(
    'corehq.apps.export.models.new.get_request_domain',
    return_value=MockRequest(domain='my-domain'),
)
class TestFormExportInstanceGeneration(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestFormExportInstanceGeneration, cls).setUpClass()
        cls.app_id = '1234'
        cls.schema = FormExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        MultipleChoiceItem(
                            path=[PathNode(name='data'), PathNode(name='question1')],
                            label='Question 1',
                            last_occurrences={cls.app_id: 3},
                        ),
                        StockItem(
                            path=[
                                PathNode(name='data'),
                                PathNode(name='balance:question-id'),
                                PathNode(name='@type'),
                            ],
                            label='Stock 1',
                            last_occurrences={cls.app_id: 3},
                        )
                    ],
                    last_occurrences={cls.app_id: 3},
                ),
                ExportGroupSchema(
                    path=[PathNode(name='data'), PathNode(name='repeat', is_repeat=True)],
                    items=[
                        ExportItem(
                            path=[
                                PathNode(name='data'),
                                PathNode(name='repeat', is_repeat=True),
                                PathNode(name='q2')
                            ],
                            label='Question 2',
                            last_occurrences={cls.app_id: 2},
                        ),
                    ],
                    last_occurrences={cls.app_id: 2},
                ),
            ],
        )

    def _generate_instance(self, build_ids_and_versions, saved_export=None):
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):

            return FormExportInstance.generate_instance_from_schema(self.schema, saved_export=saved_export)

    def test_generate_instance_from_schema(self, _, __):
        """Only questions that are in the main table and of the same version should be shown"""
        instance = self._generate_instance({self.app_id: 3})

        self.assertEqual(len(instance.tables), 2)

        index, split_column = instance.tables[0].get_column(
            [PathNode(name='data'), PathNode(name='question1')],
            'MultipleChoiceItem',
            None
        )
        self.assertTrue(isinstance(split_column, SplitExportColumn))

        index, stock_column = instance.tables[0].get_column(
            [PathNode(name='data'), PathNode(name='balance:question-id'), PathNode(name='@type')],
            'StockItem',
            None
        )
        self.assertTrue(isinstance(stock_column, StockFormExportColumn))

        selected = [column for column in instance.tables[0].columns + instance.tables[1].columns if column.selected]
        selected_system_props = len([x for x in MAIN_FORM_TABLE_PROPERTIES if x.selected])
        self.assertEqual(len(selected), 2 + selected_system_props)

    def test_generate_instance_from_schema_deleted(self, _, __):
        """Given a higher app_version, all the old questions should not be shown or selected"""
        instance = self._generate_instance({self.app_id: 4})

        self.assertEqual(len(instance.tables), 2)

        selected = [column for column in instance.tables[0].columns + instance.tables[1].columns if column.selected]
        shown = [column for column in instance.tables[0].columns + instance.tables[1].columns if column.selected]
        selected_system_props = len([x for x in MAIN_FORM_TABLE_PROPERTIES if x.selected])
        self.assertEqual(len(selected), 0 + selected_system_props)
        self.assertEqual(len(shown), 0 + selected_system_props)

    def test_default_table_names(self, _, __):
        self.assertEqual(
            FormExportInstanceDefaults.get_default_table_name(MAIN_TABLE),
            "Forms"
        )
        self.assertEqual(
            FormExportInstanceDefaults.get_default_table_name([
                PathNode(name="form"),
                PathNode(name="group1"),
                PathNode(name="awesome_repeat", is_repeat=True),
            ]),
            "Repeat: awesome_repeat"
        )

    def test_export_instance_ordering(self, _, __):
        """
        Ensures that export instances order selected columns first
        """
        from corehq.apps.export.system_properties import ROW_NUMBER_COLUMN

        instance = self._generate_instance({self.app_id: 3})

        table = instance.tables[0]
        self.assertEqual(table.columns[0].item.path, ROW_NUMBER_COLUMN.item.path)
        self.assertTrue(table.columns[0].selected)

        # When we regenerate the instance the first column should no longer be this one
        table.columns[0].selected = False

        instance = self._generate_instance({self.app_id: 3}, saved_export=instance)

        table = instance.tables[0]
        self.assertNotEqual(table.columns[0].item.path, ROW_NUMBER_COLUMN.item.path)
        self.assertTrue(table.columns[0].selected)


@mock.patch(
    'corehq.apps.export.models.new.Domain.get_by_name',
    return_value=Domain(commtrack_enabled=False),
)
class TestCaseExportInstanceGeneration(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestCaseExportInstanceGeneration, cls).setUpClass()
        cls.app_id = '1234'
        cls.schema = CaseExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ScalarItem(
                            path=[PathNode(name='p1')],
                            label='p1',
                            last_occurrences={},
                        ),
                    ],
                    last_occurrences={cls.app_id: 3},
                ),
            ],
        )

        cls.new_schema = CaseExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ScalarItem(
                            path=[PathNode(name='p1')],
                            label='p1',
                            last_occurrences={},
                        ),
                        ScalarItem(
                            path=[PathNode(name='name')],
                            label='name',
                            last_occurrences={cls.app_id: 3},
                        ),
                    ],
                    last_occurrences={cls.app_id: 3},
                ),
            ],
        )

    def _generate_instance(self, build_ids_and_versions, schema, saved_export=None):
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):

            return CaseExportInstance.generate_instance_from_schema(schema, saved_export=saved_export)

    def test_generate_instance_from_schema(self, _):
        instance = self._generate_instance({self.app_id: 3}, self.schema)

        self.assertEqual(len(instance.tables), 1)
        self.assertEqual(len(instance.tables[0].columns), 21)

        # adding in 'name' shouldn't create any new columns
        instance = self._generate_instance({self.app_id: 3}, self.new_schema, instance)
        self.assertEqual(len(instance.tables), 1)
        self.assertEqual(len(instance.tables[0].columns), 21)


@mock.patch(
    'corehq.apps.export.models.new.get_request_domain',
    return_value=MockRequest(domain='my-domain'),
)
@mock.patch(
    'corehq.apps.export.models.new.Domain.get_by_name',
    return_value=mock.MagicMock(),
)
class TestExportInstanceGenerationWithInferredSchema(SimpleTestCase):
    app_id = '1234'
    case_type = 'inferred'

    @classmethod
    def setUpClass(cls):
        super(TestExportInstanceGenerationWithInferredSchema, cls).setUpClass()
        cls.schema = CaseExportDataSchema(
            app_id=cls.app_id,
            case_type=cls.case_type,
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=[PathNode(name='data'), PathNode(name='case_property')],
                            label='Question 1',
                            last_occurrences={cls.app_id: 3},
                        ),
                    ],
                    last_occurrences={cls.app_id: 3},
                ),
            ],
        )
        cls.inferred_schema = InferredSchema(
            case_type=cls.case_type,
            group_schemas=[
                InferredExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=[PathNode(name='data'), PathNode(name='case_property')],
                            label='Inferred 1',
                            inferred=True
                        ),
                        ExportItem(
                            path=[PathNode(name='data'), PathNode(name='case_property_2')],
                            label='Inferred 1',
                            inferred=True
                        ),
                    ],
                    inferred=True
                ),
            ]
        )


@mock.patch(
    'corehq.apps.export.models.new.FormExportInstanceDefaults.get_default_instance_name',
    return_value='dummy-name'
)
@mock.patch(
    'corehq.apps.export.models.new.get_request_domain',
    return_value=MockRequest(domain='my-domain'),
)
class TestExportInstanceGenerationMultipleApps(SimpleTestCase):
    """Test Instance generation when the schema is made from multiple apps"""

    @classmethod
    def setUpClass(cls):
        super(TestExportInstanceGenerationMultipleApps, cls).setUpClass()
        cls.app_id = '1234'
        cls.second_app_id = '5678'
        cls.schema = FormExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=[PathNode(name='data'), PathNode(name='question1')],
                            label='Question 1',
                            last_occurrences={
                                cls.app_id: 2,
                                cls.second_app_id: 4
                            },
                        )
                    ],
                    last_occurrences={
                        cls.app_id: 2,
                        cls.second_app_id: 4,
                    },
                ),
                ExportGroupSchema(
                    path=[PathNode(name='data'), PathNode(name='repeat', is_repeat=True)],
                    items=[
                        ExportItem(
                            path=[
                                PathNode(name='data'),
                                PathNode(name='repeat', is_repeat=True),
                                PathNode(name='q2')
                            ],
                            label='Question 2',
                            last_occurrences={
                                cls.app_id: 3,
                            },
                        )
                    ],
                    last_occurrences={
                        cls.app_id: 3,
                    },
                ),
            ],
        )

    def test_ensure_that_column_is_not_deleted(self, _, __):
        """This test ensures that as long as ONE app in last_occurrences is the most recent version then the
        column is still marked as is_deleted=False
        """

        build_ids_and_versions = {
            self.app_id: 3,
            self.second_app_id: 4,
        }
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):
            instance = FormExportInstance.generate_instance_from_schema(self.schema)

        selected = [column for column in instance.tables[0].columns + instance.tables[1].columns if column.selected]
        is_advanced = [column for column in instance.tables[0].columns + instance.tables[1].columns if column.is_advanced]
        selected_system_props = len([x for x in MAIN_FORM_TABLE_PROPERTIES if x.selected])
        advanced_system_props = len([x for x in MAIN_FORM_TABLE_PROPERTIES if x.is_advanced])
        self.assertEqual(len(selected), 1 + selected_system_props)
        self.assertEqual(len(is_advanced), 0 + advanced_system_props)

    def test_ensure_that_column_is_deleted(self, _, __):
        """If both apps are out of date then, the question is indeed deleted"""
        build_ids_and_versions = {
            self.app_id: 3,
            self.second_app_id: 5,
        }
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):
            instance = FormExportInstance.generate_instance_from_schema(self.schema)

        selected = [column for column in instance.tables[0].columns + instance.tables[1].columns if column.selected]
        shown = [column for column in instance.tables[0].columns + instance.tables[1].columns if column.selected]
        selected_system_props = len([x for x in MAIN_FORM_TABLE_PROPERTIES if x.selected])
        self.assertEqual(len(selected), 0 + selected_system_props)
        self.assertEqual(len(shown), 0 + selected_system_props)


class TestExportInstanceDefaultFilters(SimpleTestCase):

    def test_default_form_values(self):
        # Confirm that FormExportInstances set the default user_types filter correctly
        form_export = FormExportInstance()
        form_export_wrapped = FormExportInstance.wrap({})
        for e in [form_export, form_export_wrapped]:
            self.assertListEqual(e.filters.user_types, [0, 5])

    def test_default_case_values(self):
        # Confirm that CaseExportInstances set the default project_data flag correctly
        case_export = CaseExportInstance()
        case_export_wrapped = CaseExportInstance.wrap({})
        for e in [case_export, case_export_wrapped]:
            self.assertTrue(e.filters.show_project_data)


class TestExportInstance(SimpleTestCase):

    def setUp(self):
        self.instance = FormExportInstance(
            tables=[
                TableConfiguration(
                    path=MAIN_TABLE
                ),
                TableConfiguration(
                    path=[PathNode(name='data', is_repeat=False), PathNode(name='repeat', is_repeat=True)],
                    columns=[
                        MultiMediaExportColumn(
                            selected=True
                        )
                    ]

                )
            ]
        )

    def test_get_table(self):
        table = self.instance.get_table(MAIN_TABLE)
        self.assertEqual(table.path, MAIN_TABLE)

        table = self.instance.get_table([
            PathNode(name='data', is_repeat=False), PathNode(name='repeat', is_repeat=True)
        ])
        self.assertEqual(
            table.path,
            [PathNode(name='data', is_repeat=False), PathNode(name='repeat', is_repeat=True)]
        )

        table = self.instance.get_table([
            PathNode(name='data', is_repeat=False), PathNode(name='DoesNotExist', is_repeat=False)
        ])
        self.assertIsNone(table)

    def test_has_multimedia(self):
        self.assertTrue(self.instance.has_multimedia)

    def test_has_multimedia_not_selected(self):
        self.instance.tables[1].columns[0].selected = False
        self.assertFalse(self.instance.has_multimedia)


@mock.patch(
    'corehq.apps.export.models.new.get_request_domain',
    return_value=MockRequest(domain='my-domain'),
)
class TestExportInstanceFromSavedInstance(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestExportInstanceFromSavedInstance, cls).setUpClass()
        cls.app_id = '1234'
        cls.schema = FormExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=[PathNode(name='data'), PathNode(name='question1')],
                            label='Question 1',
                            last_occurrences={
                                cls.app_id: 3,
                            },
                        ),
                        ExportItem(
                            path=[PathNode(name='data'), PathNode(name='@case_id')],
                            label='@case_id',
                            tag=PROPERTY_TAG_CASE,
                            last_occurrences={
                                cls.app_id: 3,
                            },
                        )
                    ],
                    last_occurrences={
                        cls.app_id: 3,
                    },
                ),
            ],
        )
        cls.new_schema = FormExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=[PathNode(name='data'), PathNode(name='question1')],
                            label='Question 1',
                            last_occurrences={
                                cls.app_id: 3,
                            },
                        ),
                        ExportItem(
                            path=[PathNode(name='data'), PathNode(name='@case_id')],
                            label='@case_id',
                            tag=PROPERTY_TAG_CASE,
                            last_occurrences={
                                cls.app_id: 3,
                            },
                        ),
                        ExportItem(
                            path=[PathNode(name='data'), PathNode(name='question3')],
                            label='Question 3',
                            last_occurrences={
                                cls.app_id: 3,
                            },
                        )
                    ],
                    last_occurrences={
                        cls.app_id: 3,
                    },
                ),
                ExportGroupSchema(
                    path=[PathNode(name='data'), PathNode(name='repeat', is_repeat=True)],
                    items=[
                        ExportItem(
                            path=[
                                PathNode(name='data'),
                                PathNode(name='repeat', is_repeat=True),
                                PathNode(name='q2')
                            ],
                            label='Question 2',
                            last_occurrences={
                                cls.app_id: 3,
                            },
                        )
                    ],
                    last_occurrences={
                        cls.app_id: 3,
                    },
                ),
            ],
        )

    def test_export_instance_from_saved(self, _):
        """This test ensures that when we build from a saved export instance that the selection that a user
        makes is still there"""
        first_non_system_property = len(TOP_MAIN_FORM_TABLE_PROPERTIES)
        build_ids_and_versions = {
            self.app_id: 3,
        }
        instance = self._get_instance(build_ids_and_versions)
        item = instance.tables[0].columns[first_non_system_property].item

        # Simulate a selection
        instance.tables[0].columns[first_non_system_property].selected = False

        instance.save()
        self.assertFalse(instance.tables[0].columns[first_non_system_property].selected)

        instance = self._update_instance(build_ids_and_versions, instance)

        self.assertEqual(len(instance.tables), 2)
        self.assertEqual(len(instance.tables[0].columns), 4 + len(MAIN_FORM_TABLE_PROPERTIES))

        # Selection from previous instance should hold the same and not revert to defaults
        idx, column = instance.tables[0].get_column(item.path, item.doc_type, item.transform)
        self.assertFalse(column.selected)

    def test_export_instance_deleted_columns_updated(self, _):
        """This test ensures that when building from a saved export that the new instance correctly labels the
        old columns as advanced
        """
        build_ids_and_versions = {
            self.app_id: 3,
        }
        instance = self._get_instance(build_ids_and_versions)

        # Every column should now be marked as advanced
        build_ids_and_versions = {
            self.app_id: 4,
        }
        instance = self._update_instance(build_ids_and_versions, instance)

        self.assertEqual(len(instance.tables), 2)
        self.assertEqual(len(instance.tables[0].columns), 4 + len(MAIN_FORM_TABLE_PROPERTIES))
        self.assertEqual(
            len([c for c in instance.tables[0].columns if c.is_advanced]),
            len([x for x in MAIN_FORM_TABLE_PROPERTIES if x.is_advanced]) + 1  # case_name
        )

    def _get_instance(self, build_ids_and_versions):
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):
            instance = FormExportInstance.generate_instance_from_schema(self.schema)
        instance.save()
        self.addCleanup(instance.delete)
        self.assertEqual(len(instance.tables), 1)
        self.assertEqual(len(instance.tables[0].columns), 3 + len(MAIN_FORM_TABLE_PROPERTIES))
        self.assertTrue(instance.tables[0].columns[len(TOP_MAIN_FORM_TABLE_PROPERTIES)].selected)
        return instance

    def _update_instance(self, build_ids_and_versions, instance):
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):
            instance = FormExportInstance.generate_instance_from_schema(
                self.new_schema,
                saved_export=instance
            )
        return instance

    def test_copy_instance(self, _):
        build_ids_and_versions = {
            self.app_id: 3,
        }
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):
            instance = FormExportInstance.generate_instance_from_schema(self.schema)

        instance.save()
        self.addCleanup(instance.delete)

        new_export = instance.copy_export()
        new_export.save()
        self.assertNotEqual(new_export._id, instance._id)
        self.assertEqual(new_export.name, '{} - Copy'.format(instance.name))
        old_json = instance.to_json()
        del old_json['name']
        del old_json['_id']
        del old_json['_rev']
        new_json = new_export.to_json()
        del new_json['name']
        del new_json['_id']
        del new_json['_rev']
        self.assertDictEqual(old_json, new_json)
