from django.test import SimpleTestCase

from corehq.apps.export.models import (
    ExportItem,
    ExportColumn,
)


class TestExportItemGeneration(SimpleTestCase):

    def setUp(self):
        self.item = ExportItem(
            path=['data', 'question1'],
            label='Question One',
            last_occurrence=3,
        )

    def test_create_default_from_export_item(self):
        column = ExportColumn.create_default_from_export_item([None], self.item, 3)

        self.assertEqual(column.show, True)
        self.assertEqual(column.label, 'Question One')
        self.assertEqual(column.selected, True)

    def test_create_default_from_export_item_deleted(self):
        column = ExportColumn.create_default_from_export_item([None], self.item, 4)

        self.assertEqual(column.show, False)
        self.assertEqual(column.label, 'Question One')
        self.assertEqual(column.selected, False)

    def test_create_default_from_export_item_not_main_table(self):
        column = ExportColumn.create_default_from_export_item(['other_table'], self.item, 3)

        self.assertEqual(column.show, True)
        self.assertEqual(column.label, 'Question One')
        self.assertEqual(column.selected, False)
