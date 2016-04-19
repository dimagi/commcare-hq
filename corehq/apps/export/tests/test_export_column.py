from django.test import SimpleTestCase

from corehq.apps.export.models import (
    ExportColumn,
    RowNumberColumn,
    CaseIndexExportColumn,
    CaseIndexItem,
    PathNode,
)


class TestExportColumn(SimpleTestCase):

    def test_valid_transform_function(self):
        col = ExportColumn(transform='deid_date')
        self.assertEqual(col.transform, 'deid_date')


class TestRowNumberColumn(SimpleTestCase):

    def test_get_headers(self):
        col = RowNumberColumn(label="row number", repeat=2)
        self.assertEqual(
            col.get_headers(),
            ['row number', 'row number__0', 'row number__1', 'row number__2']
        )

    def test_get_value_with_simple_index(self):
        col = RowNumberColumn()
        self.assertEqual(
            col.get_value({}, [], row_index=(7,)),
            ["7"]
        )

    def test_get_value_with_compound_index(self):
        col = RowNumberColumn()
        self.assertEqual(
            col.get_value({}, [], row_index=(12, 0, 6, 1)),
            ["12.0.6.1", 12, 0, 6, 1]
        )


class TestCaseIndexExportColumn(SimpleTestCase):

    def test_get_value(self):
        doc = {
            'indices': [
                {
                    'referenced_id': 'abc',
                    'referenced_type': 'RegCase',
                },
                {
                    'referenced_id': 'def',
                    'referenced_type': 'RegCase',
                },
                {
                    'referenced_id': 'notme',
                    'referenced_type': 'OtherCase',
                },
            ]
        }
        item = CaseIndexItem(path=[PathNode(name='indices'), PathNode(name='RegCase')])
        col = CaseIndexExportColumn(item=item)
        self.assertEqual(col.get_value(doc), 'abc def')

    def test_get_value_missing_index(self):
        doc = {
            'indices': []
        }
        doc2 = {}

        item = CaseIndexItem(path=[PathNode(name='indices'), PathNode(name='RegCase')])
        col = CaseIndexExportColumn(item=item)

        self.assertEqual(col.get_value(doc), '')
        self.assertEqual(col.get_value(doc2), '')
