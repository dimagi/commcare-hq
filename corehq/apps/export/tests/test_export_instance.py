import mock
from django.test import TestCase, SimpleTestCase

from corehq.apps.export.models import (
    ExportItem,
    MultipleChoiceItem,
    FormExportDataSchema,
    ExportGroupSchema,
    FormExportInstance,
    TableConfiguration,
    SplitExportColumn,
    PathNode,
    MAIN_TABLE,
    FormExportInstanceDefaults,
)
from corehq.apps.export.system_properties import MAIN_FORM_TABLE_PROPERTIES, \
    TOP_MAIN_FORM_TABLE_PROPERTIES


@mock.patch(
    'corehq.apps.export.models.new.FormExportInstanceDefaults.get_default_instance_name',
    return_value='dummy-name'
)
class TestExportInstanceGeneration(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
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
                        )
                    ],
                    last_occurrences={cls.app_id: 2},
                ),
            ],
        )

    def test_generate_instance_from_schema(self, _):
        """Only questions that are in the main table and of the same version should be shown"""
        build_ids_and_versions = {self.app_id: 3}
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
                return_value=build_ids_and_versions):

            instance = FormExportInstance.generate_instance_from_schema(self.schema)

        self.assertEqual(len(instance.tables), 2)

        index, split_column = instance.tables[0].get_column(
            [PathNode(name='data'), PathNode(name='question1')],
            'MultipleChoiceItem',
            None
        )
        self.assertTrue(isinstance(split_column, SplitExportColumn))

        selected = filter(
            lambda column: column.selected,
            instance.tables[0].columns + instance.tables[1].columns
        )
        shown = filter(
            lambda column: column.selected,
            instance.tables[0].columns + instance.tables[1].columns
        )
        selected_system_props = len([x for x in MAIN_FORM_TABLE_PROPERTIES if x.selected])
        self.assertEqual(len(selected), 1 + selected_system_props)
        self.assertEqual(len(shown), 1 + selected_system_props)

    def test_generate_instance_from_schema_deleted(self, _):
        """Given a higher app_version, all the old questions should not be shown or selected"""
        build_ids_and_versions = {self.app_id: 4}
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
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

    def test_default_table_names(self, _):
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
    'corehq.apps.export.models.new.FormExportInstanceDefaults.get_default_instance_name',
    return_value='dummy-name'
)
class TestExportInstanceGenerationMultipleApps(SimpleTestCase):
    """Test Instance generation when the schema is made from multiple apps"""

    @classmethod
    def setUpClass(cls):
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

    def test_ensure_that_column_is_not_deleted(self, _):
        """This test ensures that as long as ONE app in last_occurrences is the most recent version then the
        column is still marked as is_deleted=False
        """

        build_ids_and_versions = {
            self.app_id: 3,
            self.second_app_id: 4,
        }
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
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

    def test_ensure_that_column_is_deleted(self, _):
        """If both apps are out of date then, the question is indeed deleted"""
        build_ids_and_versions = {
            self.app_id: 3,
            self.second_app_id: 5,
        }
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
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


class TestExportInstance(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = FormExportInstance(
            tables=[
                TableConfiguration(
                    path=MAIN_TABLE
                ),
                TableConfiguration(
                    path=[PathNode(name='data', is_repeat=False), PathNode(name='repeat', is_repeat=True)],
                )
            ]
        )

    def test_get_table(self):
        table = self.schema.get_table(MAIN_TABLE)
        self.assertEqual(table.path, MAIN_TABLE)

        table = self.schema.get_table([
            PathNode(name='data', is_repeat=False), PathNode(name='repeat', is_repeat=True)
        ])
        self.assertEqual(
            table.path,
            [PathNode(name='data', is_repeat=False), PathNode(name='repeat', is_repeat=True)]
        )

        table = self.schema.get_table([
            PathNode(name='data', is_repeat=False), PathNode(name='DoesNotExist', is_repeat=False)
        ])
        self.assertIsNone(table)


class TestExportInstanceFromSavedInstance(TestCase):

    @classmethod
    def setUpClass(cls):
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

    def test_export_instance_from_saved(self):
        """This test ensures that when we build from a saved export instance that the selection that a user
        makes is still there"""
        first_non_system_property = len(TOP_MAIN_FORM_TABLE_PROPERTIES)
        build_ids_and_versions = {
            self.app_id: 3,
        }
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
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
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
                return_value=build_ids_and_versions):

            instance = FormExportInstance.generate_instance_from_schema(
                self.new_schema,
                saved_export=instance
            )

        self.assertEqual(len(instance.tables), 2)
        self.assertEqual(len(instance.tables[0].columns), 2 + len(MAIN_FORM_TABLE_PROPERTIES))
        # Selection from previous instance should hold the same and not revert to defaults
        self.assertFalse(instance.tables[0].columns[first_non_system_property].selected)

    def test_export_instance_deleted_columns_updated(self):
        """This test ensures that when building from a saved export that the new instance correctly labels the
        old columns as advanced
        """
        build_ids_and_versions = {
            self.app_id: 3,
        }
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
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
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
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
