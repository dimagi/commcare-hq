from collections import namedtuple
from django.test import SimpleTestCase
from mock import patch

from corehq.util.view_utils import absolute_reverse
from corehq.apps.export.const import (
    PLAIN_USER_DEFINED_SPLIT_TYPE,
    MULTISELCT_USER_DEFINED_SPLIT_TYPE,
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
    MultipleChoiceItem,
    Option,
)

MockLedgerValue = namedtuple('MockLedgerValue', ['product_id', 'section_id'])


class TestExportColumn(SimpleTestCase):

    def test_valid_transform_function(self):
        col = ExportColumn(transform='deid_date')
        self.assertEqual(col.transform, 'deid_date')


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
            [1, None, "b d"]
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
            [1, None],
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
    @patch('corehq.apps.export.models.new.Product.by_domain', return_value=[])
    def test_get_headers(self, _, __):
        column = StockExportColumn(
            domain=self.domain,
            label="Stock",
            item=ExportItem(),
        )
        get_ledger_path = (
            'corehq.form_processor.interfaces.dbaccessors.'
            'LedgerAccessors.get_ledger_values_for_product_ids'
        )
        with patch(
                get_ledger_path,
                return_value=[
                    MockLedgerValue(section_id='abc', product_id='def'),
                    MockLedgerValue(section_id='abc', product_id='def'),
                    MockLedgerValue(section_id='123', product_id='456'),
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


class TestMultiMediaExportColumn(SimpleTestCase):

    def test_get_value(self):
        column = MultiMediaExportColumn(
            item=MultiMediaItem(
                path=[PathNode(name='form'), PathNode(name='photo')],
            ),
        )

        result = column.get_value('my-domain', '1234', {'photo': '1234.jpg'}, [PathNode(name='form')])
        self.assertEqual(
            result,
            '{}?attachment=1234.jpg'.format(
                absolute_reverse('download_attachment', args=('my-domain', '1234'))
            )
        )

    def test_get_value_excel_format(self):
        column = MultiMediaExportColumn(
            item=MultiMediaItem(
                path=[PathNode(name='form'), PathNode(name='photo')],
            ),
        )

        result = column.get_value(
            'my-domain',
            '1234',
            {'photo': '1234.jpg'},
            [PathNode(name='form')],
            transform_dates=True,
        )
        self.assertEqual(
            result,
            '=HYPERLINK("{}?attachment=1234.jpg")'.format(
                absolute_reverse('download_attachment', args=('my-domain', '1234'))
            )
        )
