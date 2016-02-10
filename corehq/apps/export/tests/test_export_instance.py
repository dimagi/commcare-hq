import mock
from django.test import TestCase, SimpleTestCase

from corehq.apps.export.models import (
    ExportItem,
    FormExportDataSchema,
    ExportGroupSchema,
    FormExportInstance,
    TableConfiguration,
)
from corehq.apps.export.const import MAIN_TABLE


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
                            path=['data', 'repeat', 'q2'],
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

        selected = filter(
            lambda column: column.selected,
            instance.tables[0].columns + instance.tables[1].columns
        )
        shown = filter(
            lambda column: column.selected,
            instance.tables[0].columns + instance.tables[1].columns
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(len(shown), 1)

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
        self.assertEqual(len(selected), 0)
        self.assertEqual(len(shown), 0)


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
                            path=['data', 'question1'],
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
                    path=['data', 'repeat'],
                    items=[
                        ExportItem(
                            path=['data', 'repeat', 'q2'],
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
        self.assertEqual(len(selected), 1)
        self.assertEqual(len(is_advanced), 0)

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
        self.assertEqual(len(selected), 0)
        self.assertEqual(len(shown), 0)


class TestExportInstance(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = FormExportInstance(
            tables=[
                TableConfiguration(
                    path=MAIN_TABLE
                ),
                TableConfiguration(
                    path=['data', 'repeat'],
                )
            ]
        )

    def test_get_table(self):
        table = self.schema.get_table(MAIN_TABLE)
        self.assertEqual(table.path, MAIN_TABLE)

        table = self.schema.get_table(['data', 'repeat'])
        self.assertEqual(table.path, ['data', 'repeat'])

        table = self.schema.get_table(['data', 'DoesNotExist'])
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
                            path=['data', 'question1'],
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
                            path=['data', 'question1'],
                            label='Question 1',
                            last_occurrences={
                                cls.app_id: 3,
                            },
                        ),
                        ExportItem(
                            path=['data', 'question3'],
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
                    path=['data', 'repeat'],
                    items=[
                        ExportItem(
                            path=['data', 'repeat', 'q2'],
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
        build_ids_and_versions = {
            self.app_id: 3,
        }
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
                return_value=build_ids_and_versions):
            instance = FormExportInstance.generate_instance_from_schema(self.schema)

        instance.save()
        self.assertEqual(len(instance.tables), 1)
        self.assertEqual(len(instance.tables[0].columns), 1)
        self.assertTrue(instance.tables[0].columns[0].selected)

        # Simulate a selection
        instance.tables[0].columns[0].selected = False

        instance.save()
        self.assertFalse(instance.tables[0].columns[0].selected)

        with mock.patch(
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
                return_value=build_ids_and_versions):

            instance = FormExportInstance.generate_instance_from_schema(
                self.new_schema,
                saved_export=instance
            )

        self.assertEqual(len(instance.tables), 2)
        self.assertEqual(len(instance.tables[0].columns), 2)
        # Selection from previous instance should hold the same and not revert to defaults
        self.assertFalse(instance.tables[0].columns[0].selected)

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
        self.assertEqual(len(instance.tables[0].columns), 1)
        self.assertTrue(instance.tables[0].columns[0].selected)

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
        self.assertEqual(len(instance.tables[0].columns), 2)
        self.assertEqual(len(filter(lambda c: c.is_advanced, instance.tables[0].columns)), 2)
