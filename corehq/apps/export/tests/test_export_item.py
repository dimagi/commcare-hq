from django.test import SimpleTestCase

from corehq.apps.export.const import CASE_NAME_TRANSFORM
from corehq.apps.export.models import (
    ExportItem,
    ExportColumn,
)
from corehq.apps.export.models.new import MAIN_TABLE, SystemExportItem


class TestExportItemGeneration(SimpleTestCase):
    app_id = '1234'

    def setUp(self):
        self.item = ExportItem(
            path=['data', 'question1'],
            label='Question One',
            last_occurrences={self.app_id: 3},
        )

    def test_create_default_from_export_item(self):
        column = ExportColumn.create_default_from_export_item(MAIN_TABLE, self.item, {self.app_id: 3})

        self.assertEqual(column.is_advanced, False)
        self.assertEqual(column.label, 'Question One')
        self.assertEqual(column.selected, True)

    def test_create_default_from_system_export_item(self):
        column = ExportColumn.create_default_from_export_item(
            MAIN_TABLE,
            SystemExportItem(
                path=['form', 'meta', 'userID'],
                label='userID',
                is_advanced=True,
                last_occurrences={self.app_id: 3},
            ),
            {self.app_id: 3}
        )

        self.assertEqual(column.is_advanced, True)
        self.assertEqual(column.label, 'userID')
        self.assertEqual(column.selected, False)

    def test_create_default_from_export_item_deleted(self):
        column = ExportColumn.create_default_from_export_item(MAIN_TABLE, self.item, {self.app_id: 4})

        self.assertEqual(column.is_advanced, True)
        self.assertEqual(column.label, 'Question One')
        self.assertEqual(column.selected, False)

    def test_create_default_from_export_item_not_main_table(self):
        column = ExportColumn.create_default_from_export_item(['other_table'], self.item, {self.app_id: 3})

        self.assertEqual(column.is_advanced, False)
        self.assertEqual(column.label, 'Question One')
        self.assertEqual(column.selected, False)

    def test_wrap_export_item(self):
        path = ["foo", "bar"]
        item = ExportItem(path=path)
        wrapped = ExportItem.wrap(item.to_json())
        self.assertEqual(type(wrapped), type(item))
        self.assertEqual(wrapped.to_json(), item.to_json())

    def test_wrap_export_item_child(self):
        path = ["foo", "bar"]
        is_advanced = True
        transform = CASE_NAME_TRANSFORM
        item = SystemExportItem(path=path, is_advanced=is_advanced, transform=transform)
        wrapped = ExportItem.wrap(item.to_json())
        self.assertEqual(type(wrapped), type(item))
        self.assertEqual(wrapped.to_json(), item.to_json())
