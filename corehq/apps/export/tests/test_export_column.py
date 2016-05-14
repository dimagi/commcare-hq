from django.test import SimpleTestCase

from corehq.util.view_utils import absolute_reverse
from corehq.apps.export.const import (
    PLAIN_USER_DEFINED_SPLIT_TYPE,
    MULTISELCT_USER_DEFINED_SPLIT_TYPE,
)
from corehq.apps.export.models import (
    ExportColumn,
    RowNumberColumn,
    CaseIndexExportColumn,
    CaseIndexItem,
    MultiMediaExportColumn,
    MultiMediaItem,
    PathNode,
    SplitGPSExportColumn,
    GeopointItem,
    ExportItem,
    SplitUserDefinedExportColumn,
    SplitExportColumn,
    MultipleChoiceItem,
    Option,
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
            col.get_value('domain', 'docid', {}, [], row_index=(7,)),
            ["7"]
        )

    def test_get_value_with_compound_index(self):
        col = RowNumberColumn()
        self.assertEqual(
            col.get_value('domain', 'docid', {}, [], row_index=(12, 0, 6, 1)),
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
        self.assertEqual(col.get_value('domain', 'docid', doc), 'abc def')

    def test_get_value_missing_index(self):
        doc = {
            'indices': []
        }
        doc2 = {}

        item = CaseIndexItem(path=[PathNode(name='indices'), PathNode(name='RegCase')])
        col = CaseIndexExportColumn(item=item)

        self.assertEqual(col.get_value('domain', 'docid', doc), '')
        self.assertEqual(col.get_value('domain', 'docid', doc2), '')


class TestGeopointExportColumn(SimpleTestCase):

    def test_get_value(self):
        column = SplitGPSExportColumn(
            item=GeopointItem(path=[PathNode(name='form'), PathNode(name='geo')])
        )
        result = column.get_value('domain', 'docid', {'form': {'geo': '10 20'}}, [], split_column=True)
        self.assertEqual(result, ['10', '20', None, None])

        result = column.get_value('domain', 'docid', {'form': {'geo': '10 20'}}, [], split_column=False)
        self.assertEqual(result, '10 20')

    def test_get_headers(self):
        column = SplitGPSExportColumn(
            item=GeopointItem(path=[PathNode(name='form'), PathNode(name='geo')]),
            label='geo-label',
        )
        result = column.get_headers(split_column=True)
        self.assertEqual(len(result), 4)

        result = column.get_headers(split_column=False)
        self.assertEqual(result, ['geo-label'])


class TestSplitUserDefinedExportColumn(SimpleTestCase):

    def test_get_value(self):
        column = SplitUserDefinedExportColumn(
            split_type=MULTISELCT_USER_DEFINED_SPLIT_TYPE,
            item=ExportItem(path=[PathNode(name='form'), PathNode(name='mc')]),
            user_defined_options=['one', 'two', 'three'],
        )
        result = column.get_value('domain', 'docid', {'form': {'mc': 'one two extra'}}, [])
        self.assertEqual(result, [1, 1, None, 'extra'])

        column.split_type = PLAIN_USER_DEFINED_SPLIT_TYPE
        result = column.get_value('domain', 'docid', {'form': {'mc': 'one two extra'}}, [])
        self.assertEqual(result, 'one two extra')

    def test_get_headers(self):
        column = SplitUserDefinedExportColumn(
            split_type=MULTISELCT_USER_DEFINED_SPLIT_TYPE,
            item=ExportItem(path=[PathNode(name='form'), PathNode(name='mc')]),
            user_defined_options=['one', 'two', 'three'],
            label='form.mc',
        )
        result = column.get_headers()
        self.assertEqual(
            result,
            ['form.mc | one', 'form.mc | two', 'form.mc | three', 'form.mc | extra']
        )

        column.split_type = PLAIN_USER_DEFINED_SPLIT_TYPE
        result = column.get_headers()
        self.assertEqual(result, ['form.mc'])


class TestSplitExportColumn(SimpleTestCase):

    def test_get_value(self):
        column = SplitExportColumn(
            item=MultipleChoiceItem(
                path=[PathNode(name='form'), PathNode(name='mc')],
                options=[Option(value="foo"), Option(value="bar")]
            ),
        )
        result = column.get_value('domain', 'docid', {'form': {'mc': 'foo extra'}}, [], split_column=True)
        self.assertEqual(result, [1, None, 'extra'])

        result = column.get_value('domain', 'docid', {'form': {'mc': 'foo extra'}}, [], split_column=False)
        self.assertEqual(result, 'foo extra')

    def test_get_headers(self):
        column = SplitExportColumn(
            item=MultipleChoiceItem(
                path=[PathNode(name='form'), PathNode(name='mc')],
                options=[Option(value="foo"), Option(value="bar")]
            ),
            label='form.mc'
        )
        result = column.get_headers(split_column=True)
        self.assertEqual(
            result,
            ['form.mc | foo', 'form.mc | bar', 'form.mc | extra']
        )

        result = column.get_headers(split_column=False)
        self.assertEqual(result, ['form.mc'])
