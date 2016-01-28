from django.test import SimpleTestCase

from corehq.apps.export.models import (
    ExportItem,
    ExportDataSchema,
    ExportGroupSchema,
    ExportInstance,
)


class TestExportInstanceGeneration(SimpleTestCase):

    def setUp(self):
        self.app_id = '1234'
        self.schema = ExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=[None],
                    items=[
                        ExportItem(
                            path=['data', 'question1'],
                            label='Question 1',
                            last_occurrence={self.app_id: 3},
                        )
                    ],
                    last_occurrence={self.app_id: 3},
                ),
                ExportGroupSchema(
                    path=['data', 'repeat'],
                    items=[
                        ExportItem(
                            path=['data', 'repeat', 'q2'],
                            label='Question 2',
                            last_occurrence={self.app_id: 2},
                        )
                    ],
                    last_occurrence={self.app_id: 2},
                ),
            ],
        )

    def test_generate_instance_from_schema(self):
        """Only questions that are in the main table and of the same version should be shown"""
        instance = ExportInstance.generate_instance_from_schema(self.schema, 3)

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
        instance = ExportInstance.generate_instance_from_schema(self.schema, 4)

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
