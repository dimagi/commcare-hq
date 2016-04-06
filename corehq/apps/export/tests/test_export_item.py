from django.test import SimpleTestCase

from corehq.apps.export.models import (
    ExportItem,
    ExportColumn,
    GeopointItem,
    Option, MultipleChoiceItem)
from corehq.apps.export.models.new import (
    MAIN_TABLE,
    PathNode,
)


class TestExportItemGeneration(SimpleTestCase):
    app_id = '1234'

    def setUp(self):
        self.item = ExportItem(
            path=[PathNode(name='data'), PathNode(name='question1')],
            label='Question One',
            last_occurrences={self.app_id: 3},
        )

    def test_create_default_from_export_item(self):
        column = ExportColumn.create_default_from_export_item(MAIN_TABLE, self.item, {self.app_id: 3})

        self.assertEqual(column.is_advanced, False)
        self.assertEqual(column.label, 'data.question1')
        self.assertEqual(column.selected, True)

    def test_create_default_from_export_item_deleted(self):
        column = ExportColumn.create_default_from_export_item(MAIN_TABLE, self.item, {self.app_id: 4})

        self.assertEqual(column.is_advanced, True)
        self.assertEqual(column.label, 'data.question1')
        self.assertEqual(column.selected, False)

    def test_create_default_from_export_item_not_main_table(self):
        column = ExportColumn.create_default_from_export_item(['other_table'], self.item, {self.app_id: 3})

        self.assertEqual(column.is_advanced, False)
        self.assertEqual(column.label, 'data.question1')
        self.assertEqual(column.selected, False)

    def test_wrap_export_item(self):
        path = [PathNode(name="foo"), PathNode(name="bar")]
        item = ExportItem(path=path)
        wrapped = ExportItem.wrap(item.to_json())
        self.assertEqual(type(wrapped), type(item))
        self.assertEqual(wrapped.to_json(), item.to_json())

    def test_wrap_export_item_child(self):
        path = [PathNode(name="foo"), PathNode(name="bar")]
        item = MultipleChoiceItem(path=path, options=[Option(value="foo")])
        wrapped = ExportItem.wrap(item.to_json())
        self.assertEqual(type(wrapped), type(item))
        self.assertEqual(wrapped.to_json(), item.to_json())


def TestGeopointItem(SimpleTestCase):

    def test_split_value(self):
        item = GeopointItem(path=[PathNode(name='form'), PathNode(name='geo')])
        result = item.split_value('10 15', False)
        self.assertEqual(result, ['10', '15', None, None])

        result = item.split_value('10 15 2 2', False)
        self.assertEqual(result, ['10', '15', '2', '2'])

    def test_split_header(self):
        item = GeopointItem(path=[PathNode(name='form'), PathNode(name='geo')])
        headers = item.split_header('geo', False)
        self.assertEqual(len(headers), 4)
