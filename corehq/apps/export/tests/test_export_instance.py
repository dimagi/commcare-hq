import mock
from django.test import SimpleTestCase

from corehq.apps.export.models import (
    ExportItem,
    ExportDataSchema,
    ExportGroupSchema,
    ExportInstance,
)


class TestExportInstanceGeneration(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.app_id = '1234'
        cls.schema = ExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=[None],
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

    def test_generate_instance_from_schema(self):
        """Only questions that are in the main table and of the same version should be shown"""
        build_ids_and_versions = {self.app_id: 3}
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
                return_value=build_ids_and_versions):

            instance = ExportInstance.generate_instance_from_schema(
                self.schema,
                'dummy',
                self.app_id
            )

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

    def test_generate_instance_from_schema_deleted(self):
        """Given a higher app_version, all the old questions should not be shown or selected"""
        build_ids_and_versions = {self.app_id: 4}
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
                return_value=build_ids_and_versions):
            instance = ExportInstance.generate_instance_from_schema(
                self.schema,
                'dummy',
                self.app_id
            )

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


class TestExportInstanceGenerationMultipleApps(SimpleTestCase):
    """Test Instance generation when the schema is made from multiple apps"""

    @classmethod
    def setUpClass(cls):
        cls.app_id = '1234'
        cls.second_app_id = '5678'
        cls.schema = ExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=[None],
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

    def test_ensure_that_column_is_not_deleted(self):
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
            instance = ExportInstance.generate_instance_from_schema(self.schema, 'dummy-domain')

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

    def test_ensure_that_column_is_deleted(self):
        """If both apps are out of date then, the question is indeed deleted"""
        build_ids_and_versions = {
            self.app_id: 3,
            self.second_app_id: 5,
        }
        with mock.patch(
                'corehq.apps.export.models.new.get_latest_built_app_ids_and_versions',
                return_value=build_ids_and_versions):
            instance = ExportInstance.generate_instance_from_schema(self.schema, 'dummy-domain')

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
