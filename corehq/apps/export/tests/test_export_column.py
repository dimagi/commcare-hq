from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from django.test import SimpleTestCase
from mock import patch

from corehq.util.view_utils import absolute_reverse
from corehq.apps.export.const import (
    PLAIN_USER_DEFINED_SPLIT_TYPE,
    MULTISELCT_USER_DEFINED_SPLIT_TYPE,
    MISSING_VALUE,
    EMPTY_VALUE,
)
from corehq.apps.export.models import (
    ExportColumn,
    StockExportColumn,
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
    UserDefinedExportColumn,
    MultipleChoiceItem,
    Option,
)

MockLedgerValue = namedtuple('MockLedgerValue', ['entry_id', 'section_id'])


class TestExportColumn(SimpleTestCase):

    def test_valid_transform_function(self):
        col = ExportColumn(transform='deid_date')
        self.assertEqual(col.transform, 'deid_date')

    def test_get_value(self):
        column = ExportColumn(
            item=ExportItem(
                path=[PathNode(name='form'), PathNode(name='q1')],
            ),
        )
        doc = {"q1": "answer"}
        self.assertEqual(
            column.get_value('domain', 'docid', doc, [PathNode(name='form')]),
            "answer",
        )

    def test_get_value_with_text(self):
        column = ExportColumn(
            item=ExportItem(
                path=[PathNode(name='form'), PathNode(name='q1')],
            ),
        )
        doc = {"q1": {'#text': "answer"}}
        self.assertEqual(
            column.get_value('domain', 'docid', doc, [PathNode(name='form')]),
            "answer",
        )


class SplitColumnTest(SimpleTestCase):

    def test_get_value(self):
        column = SplitExportColumn(
            item=MultipleChoiceItem(
                path=[PathNode(name='form'), PathNode(name='q1')],
                options=[Option(value='a'), Option(value='c')]
            ),
            ignore_unspecified_options=False
        )
        doc = {"q1": "a b d"}
        self.assertEqual(column.get_value(
            'domain',
            'docid',
            doc,
            [PathNode(name='form')],
            split_column=True),
            [1, EMPTY_VALUE, "b d"]
        )

        doc = {}
        self.assertEqual(
            column.get_value(
                'domain',
                'docid',
                doc,
                [PathNode(name='form')],
                split_column=True
            ),
            [MISSING_VALUE, MISSING_VALUE, MISSING_VALUE]
        )

    def test_get_value_numerical(self):
        column = SplitExportColumn(
            item=MultipleChoiceItem(
                path=[PathNode(name='form'), PathNode(name='q1')],
                options=[Option(value='1'), Option(value='2')]
            ),
            ignore_unspecified_options=False
        )
        doc = {"q1": 3}
        self.assertEqual(column.get_value(
            'domain',
            'docid',
            doc,
            [PathNode(name='form')],
            split_column=True),
            [EMPTY_VALUE, EMPTY_VALUE, 3]
        )

    def test_ignore_extas(self):
        column = SplitExportColumn(
            item=MultipleChoiceItem(
                path=[PathNode(name='form'), PathNode(name='q1')],
                options=[Option(value='a'), Option(value='c')]
            ),
            ignore_unspecified_options=True
        )
        doc = {"q1": "a b d"}
        self.assertEqual(column.get_value(
            'domain',
            'docid',
            doc,
            [PathNode(name="form")],
            split_column=True),
            [1, EMPTY_VALUE],
        )
        doc = {}
        self.assertEqual(
            column.get_value(
                'domain',
                'docid',
                doc,
                [PathNode(name='form')],
                split_column=True
            ),
            [MISSING_VALUE, MISSING_VALUE]
        )

    def test_basic_get_headers(self):
        column = SplitExportColumn(
            label="Fruit",
            item=MultipleChoiceItem(
                options=[Option(value='Apple'), Option(value='Banana')]
            ),
            ignore_unspecified_options=True
        )
        self.assertEqual(column.get_headers(split_column=True), ["Fruit | Apple", "Fruit | Banana"])

    def test_get_headers_with_template_string(self):
        column = SplitExportColumn(
            label="Fruit - {option}",
            item=MultipleChoiceItem(
                options=[Option(value='Apple'), Option(value='Banana')]
            ),
            ignore_unspecified_options=True
        )
        self.assertEqual(column.get_headers(split_column=True), ["Fruit - Apple", "Fruit - Banana"])

    def test_get_headers_with_extras(self):
        column = SplitExportColumn(
            label="Fruit - {option}",
            item=MultipleChoiceItem(
                options=[Option(value='Apple'), Option(value='Banana')]
            ),
            ignore_unspecified_options=False
        )
        self.assertEqual(
            column.get_headers(split_column=True),
            ["Fruit - Apple", "Fruit - Banana", "Fruit - extra"]
        )


class StockExportColumnTest(SimpleTestCase):
    domain = 'stock-domain'

    @patch('corehq.apps.export.models.new.StockExportColumn._get_product_name', return_value='water')
    def test_get_headers(self, _):
        column = StockExportColumn(
            domain=self.domain,
            label="Stock",
            item=ExportItem(),
        )
        with patch(
                'corehq.apps.export.models.new.get_ledger_section_entry_combinations',
                return_value=[
                    MockLedgerValue(section_id='abc', entry_id='def'),
                    MockLedgerValue(section_id='abc', entry_id='def'),
                    MockLedgerValue(section_id='123', entry_id='456'),
                ]):

            headers = list(column.get_headers())
            self.assertEqual(headers, ['water (123)', 'water (abc)'])


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
        self.assertEqual(col.get_value('domain', 'docid', doc, []), 'abc def')

    def test_get_value_missing_index(self):
        doc = {
            'indices': []
        }
        doc2 = {}

        item = CaseIndexItem(path=[PathNode(name='indices'), PathNode(name='RegCase')])
        col = CaseIndexExportColumn(item=item)

        self.assertEqual(col.get_value('domain', 'docid', doc, []), EMPTY_VALUE)
        self.assertEqual(col.get_value('domain', 'docid', doc2, []), EMPTY_VALUE)


class TestGeopointExportColumn(SimpleTestCase):

    def test_get_value(self):
        column = SplitGPSExportColumn(
            item=GeopointItem(path=[PathNode(name='form'), PathNode(name='geo')])
        )
        result = column.get_value('domain', 'docid', {'form': {'geo': '10 20'}}, [], split_column=True)
        self.assertEqual(result, ['10', '20', EMPTY_VALUE, EMPTY_VALUE])

        result = column.get_value('domain', 'docid', {'form': {'geo': '10 20'}}, [], split_column=False)
        self.assertEqual(result, '10 20')

        result = column.get_value('domain', 'docid', {'form': {'geo': None}}, [], split_column=True)
        self.assertEqual(result, [MISSING_VALUE] * 4)

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
        self.assertEqual(result, [1, EMPTY_VALUE, 'extra'])

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


class TestMultiMediaExportColumn(SimpleTestCase):
    column = MultiMediaExportColumn(
        item=MultiMediaItem(
            path=[PathNode(name='form'), PathNode(name='photo')],
        ),
    )

    def test_get_value(self):
        doc = {'external_blobs': {'1234.jpg': {}},
               'photo': '1234.jpg'}
        result = self.column.get_value('my-domain', '1234', doc, [PathNode(name='form')])
        self.assertEqual(
            result,
            absolute_reverse('api_form_attachment', args=('my-domain', '1234', '1234.jpg'))
        )

    def test_missing_value(self):
        doc = {'external_blobs': {},
               'photo': None}
        result = self.column.get_value('my-domain', '1234', doc, [PathNode(name='form')])
        self.assertEqual(result, MISSING_VALUE)

    def test_empty_string(self):
        doc = {'external_blobs': {},
               'photo': ''}
        result = self.column.get_value('my-domain', '1234', doc, [PathNode(name='form')])
        self.assertEqual(result, '')

    def test_mismatched_value_type(self):
        doc = {'external_blobs': {},
               'photo': "this clearly isn't a photo"}
        result = self.column.get_value('my-domain', "this clearly isn't a photo", doc, [PathNode(name='form')])
        self.assertEqual(result, "this clearly isn't a photo")

    def test_get_value_excel_format(self):
        doc = {'external_blobs': {'1234.jpg': {}},
               'photo': '1234.jpg'}
        result = self.column.get_value(
            'my-domain',
            '1234',
            doc,
            [PathNode(name='form')],
            transform_dates=True,
        )
        self.assertEqual(
            result,
            '=HYPERLINK("{}")'.format(
                absolute_reverse('api_form_attachment', args=('my-domain', '1234', '1234.jpg'))
            )
        )


class TestUserDefinedExportColumn(SimpleTestCase):

    def test_get_value(self):
        column = UserDefinedExportColumn(
            custom_path=[
                PathNode(name='form'),
                PathNode(name='question1'),
            ]
        )

        result = column.get_value(
            'my-domain',
            '1234',
            {'question1': '1234'},
            [PathNode(name='form')]
        )
        self.assertEqual(
            result,
            '1234',
        )
