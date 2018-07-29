from __future__ import absolute_import
from __future__ import unicode_literals
import mock
from django.test import SimpleTestCase
from collections import namedtuple

from corehq.apps.export.models import (
    ExportItem,
    ExportColumn,
    Option, MultipleChoiceItem)
from corehq.apps.export.models.new import (
    MAIN_TABLE,
    PathNode,
)

MockRequest = namedtuple('MockRequest', 'domain')


@mock.patch(
    'corehq.apps.export.models.new.get_request_domain',
    return_value=MockRequest(domain='my-domain'),
)
class TestExportItemGeneration(SimpleTestCase):
    app_id = '1234'

    def setUp(self):
        self.item = ExportItem(
            path=[PathNode(name='data'), PathNode(name='question1')],
            label='Question One',
            last_occurrences={self.app_id: 3},
        )

    def test_create_default_from_export_item(self, _):
        column = ExportColumn.create_default_from_export_item(MAIN_TABLE, self.item, {self.app_id: 3})

        self.assertEqual(column.is_advanced, False)
        self.assertEqual(column.is_deleted, False)
        self.assertEqual(column.label, 'data.question1')
        self.assertEqual(column.selected, True)

    def test_create_default_from_export_item_deleted(self, _):
        column = ExportColumn.create_default_from_export_item(MAIN_TABLE, self.item, {self.app_id: 4})

        self.assertEqual(column.is_advanced, False)
        self.assertEqual(column.is_deleted, True)
        self.assertEqual(column.label, 'data.question1')
        self.assertEqual(column.selected, False)

    def test_create_default_from_export_item_not_main_table(self, _):
        column = ExportColumn.create_default_from_export_item(['other_table'], self.item, {self.app_id: 3})

        self.assertEqual(column.is_advanced, False)
        self.assertEqual(column.is_deleted, False)
        self.assertEqual(column.label, 'data.question1')
        self.assertEqual(column.selected, False)

    def test_wrap_export_item(self, _):
        path = [PathNode(name="foo"), PathNode(name="bar")]
        item = ExportItem(path=path)
        wrapped = ExportItem.wrap(item.to_json())
        self.assertEqual(type(wrapped), type(item))
        self.assertEqual(wrapped.to_json(), item.to_json())

    def test_wrap_export_item_child(self, _):
        path = [PathNode(name="foo"), PathNode(name="bar")]
        item = MultipleChoiceItem(path=path, options=[Option(value="foo")])
        wrapped = ExportItem.wrap(item.to_json())
        self.assertEqual(type(wrapped), type(item))
        self.assertEqual(wrapped.to_json(), item.to_json())
