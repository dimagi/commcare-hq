import mock
from collections import namedtuple
from django.test import TestCase, SimpleTestCase

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
)
from corehq.apps.export.models.new import ExportInstanceFilters
from corehq.apps.export.system_properties import MAIN_FORM_TABLE_PROPERTIES, \
    TOP_MAIN_FORM_TABLE_PROPERTIES

MockRequest = namedtuple('MockRequest', 'domain')


@mock.patch(
    'corehq.apps.export.models.new.FormExportInstanceDefaults.get_default_instance_name',
    return_value='dummy-name'
)
@mock.patch(
    'corehq.apps.export.models.new.get_request',
    return_value=MockRequest(domain='my-domain'),
)
class TestExportInstanceGeneration(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestExportInstanceGeneration, cls).setUpClass()
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

    def test_generate_instance_from_schema(self, _, __):
        """Only questions that are in the main table and of the same version should be shown"""
        build_ids_and_versions = {self.app_id: 3}
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):

            instance = FormExportInstance.generate_instance_from_schema(self.schema)

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

        selected = filter(
            lambda column: column.selected,
            instance.tables[0].columns + instance.tables[1].columns
        )
        selected_system_props = len([x for x in MAIN_FORM_TABLE_PROPERTIES if x.selected])
        self.assertEqual(len(selected), 2 + selected_system_props)

    def test_generate_instance_from_schema_deleted(self, _, __):
        """Given a higher app_version, all the old questions should not be shown or selected"""
        build_ids_and_versions = {self.app_id: 4}
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):
            instance = FormExportInstance.generate_instance_from_schema(self.schema)

        self.assertEqual(len(instance.tables), 2)

        selected = filter(
            lambda column: column.selected,
            instance.tables[0].columns + instance.tables[1].columns
        )
        shown = filter(
            lambda column: column.selected,
            instance.tables[0].columns + instance.tables[1].columns
        )
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


@mock.patch(
    'corehq.apps.export.models.new.get_request',
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
    'corehq.apps.export.models.new.get_request',
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

        selected = filter(
            lambda column: column.selected,
            instance.tables[0].columns + instance.tables[1].columns
        )
        is_advanced = filter(
            lambda column: column.is_advanced,
            instance.tables[0].columns + instance.tables[1].columns
        )
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

        selected = filter(
            lambda column: column.selected,
            instance.tables[0].columns + instance.tables[1].columns
        )
        shown = filter(
            lambda column: column.selected,
            instance.tables[0].columns + instance.tables[1].columns
        )
        selected_system_props = len([x for x in MAIN_FORM_TABLE_PROPERTIES if x.selected])
        self.assertEqual(len(selected), 0 + selected_system_props)
        self.assertEqual(len(shown), 0 + selected_system_props)


class TestExportInstanceDefaultFilters(SimpleTestCase):

    def test_default_form_values(self):
        # Confirm that FormExportInstances set the default user_types filter correctly
        form_export = FormExportInstance()
        form_export_wrapped = FormExportInstance.wrap({})
        for e in [form_export, form_export_wrapped]:
            self.assertListEqual(e.filters.user_types, [0])

    def test_default_case_values(self):
        # Confirm that CaseExportInstances set the default show_all_data flag correctly
        case_export = CaseExportInstance()
        case_export_wrapped = CaseExportInstance.wrap({})
        for e in [case_export, case_export_wrapped]:
            self.assertTrue(e.filters.show_all_data)

    def test_explicit_values(self):
        # Confirm that FormExportInstances do not override export instance filters passed explicitly
        e1 = FormExportInstance(filters=ExportInstanceFilters())
        e2 = FormExportInstance({'filters': {}})
        e3 = FormExportInstance.wrap({'filters': {}})
        for e in [e1, e2, e3]:
            self.assertListEqual(e.filters.user_types, [])


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
    'corehq.apps.export.models.new.get_request',
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
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):
            instance = FormExportInstance.generate_instance_from_schema(self.schema)

        instance.save()
        self.assertEqual(len(instance.tables), 1)
        self.assertEqual(len(instance.tables[0].columns), 1 + len(MAIN_FORM_TABLE_PROPERTIES))
        self.assertTrue(instance.tables[0].columns[first_non_system_property].selected)

        # Simulate a selection
        instance.tables[0].columns[first_non_system_property].selected = False

        instance.save()
        self.assertFalse(instance.tables[0].columns[first_non_system_property].selected)

        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):

            instance = FormExportInstance.generate_instance_from_schema(
                self.new_schema,
                saved_export=instance
            )

        self.assertEqual(len(instance.tables), 2)
        self.assertEqual(len(instance.tables[0].columns), 2 + len(MAIN_FORM_TABLE_PROPERTIES))
        # Selection from previous instance should hold the same and not revert to defaults
        self.assertFalse(instance.tables[0].columns[first_non_system_property].selected)

    def test_export_instance_deleted_columns_updated(self, _):
        """This test ensures that when building from a saved export that the new instance correctly labels the
        old columns as advanced
        """
        build_ids_and_versions = {
            self.app_id: 3,
        }
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):
            instance = FormExportInstance.generate_instance_from_schema(self.schema)

        instance.save()
        self.assertEqual(len(instance.tables), 1)
        self.assertEqual(len(instance.tables[0].columns), 1 + len(MAIN_FORM_TABLE_PROPERTIES))
        self.assertTrue(instance.tables[0].columns[len(TOP_MAIN_FORM_TABLE_PROPERTIES)].selected)

        # Every column should now be marked as advanced
        build_ids_and_versions = {
            self.app_id: 4,
        }
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_app_ids_and_versions',
                return_value=build_ids_and_versions):

            instance = FormExportInstance.generate_instance_from_schema(
                self.new_schema,
                saved_export=instance
            )

        self.assertEqual(len(instance.tables), 2)
        self.assertEqual(len(instance.tables[0].columns), 2 + len(MAIN_FORM_TABLE_PROPERTIES))
        self.assertEqual(
            len(filter(lambda c: c.is_advanced, instance.tables[0].columns)),
            2 + len([x for x in MAIN_FORM_TABLE_PROPERTIES if x.is_advanced])
        )
