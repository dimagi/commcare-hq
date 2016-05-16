from collections import namedtuple
from mock import patch
from django.test import SimpleTestCase

from corehq.apps.export.const import USERNAME_TRANSFORM
from corehq.apps.export.models import TableConfiguration, ExportColumn, \
    ScalarItem, ExportRow
from corehq.apps.export.models.new import (
    SplitExportColumn,
    MultipleChoiceItem,
    Option,
    DocRow,
    RowNumberColumn,
    PathNode,
    StockExportColumn,
    ExportItem,
)

MockLedgerValue = namedtuple('MockLedgerValue', ['product_id', 'section_id'])


class TableConfigurationTest(SimpleTestCase):

    def test_get_column(self):
        table_configuration = TableConfiguration(
            path=[PathNode(name='form', is_repeat=False), PathNode(name="repeat1", is_repeat=True)],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=[
                            PathNode(name='form'),
                            PathNode(name='repeat1', is_repeat=True),
                            PathNode(name='q1')
                        ],
                    )
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=[
                            PathNode(name="form"),
                            PathNode(name="user_id"),
                        ],
                        transform=USERNAME_TRANSFORM
                    )
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=[
                            PathNode(name='form'),
                            PathNode(name='repeat1', is_repeat=True),
                            PathNode(name='q2')
                        ],
                    )
                ),
            ]
        )

        index, column = table_configuration.get_column(
            [
                PathNode(name='form'),
                PathNode(name='repeat1', is_repeat=True),
                PathNode(name='q1')
            ],
            'ScalarItem',
            None,
        )
        self.assertEqual(
            column.item.path,
            [
                PathNode(name='form'),
                PathNode(name='repeat1', is_repeat=True),
                PathNode(name='q1')
            ]
        )
        self.assertEqual(index, 0)

        index, column = table_configuration.get_column(
            [
                PathNode(name='form'),
                PathNode(name='repeat1', is_repeat=True),
                PathNode(name='DoesNotExist')
            ],
            'ScalarItem',
            None,
        )
        self.assertIsNone(column)

        # Verify that get_column ignores deid transforms
        index, column = table_configuration.get_column(
            [PathNode(name="form"), PathNode(name="user_id")],
            'ScalarItem',
            USERNAME_TRANSFORM
        )
        self.assertIsNotNone(column)
        self.assertEqual(index, 1)


class TableConfigurationGetSubDocumentsTest(SimpleTestCase):

    def test_basic(self):

        table = TableConfiguration(path=[])
        self.assertEqual(
            table._get_sub_documents(
                {'foo': 'a'},
                0
            ),
            [
                DocRow(row=(0,), doc={'foo': 'a'})
            ]
        )

    def test_simple_repeat(self):
        table = TableConfiguration(
            path=[PathNode(name="foo", is_repeat=True)]
        )
        self.assertEqual(
            table._get_sub_documents(
                {
                    'foo': [
                        {'bar': 'a'},
                        {'bar': 'b'},
                    ]
                },
                0
            ),
            [
                DocRow(row=(0, 0), doc={'bar': 'a'}),
                DocRow(row=(0, 1), doc={'bar': 'b'})
            ]
        )

    def test_nested_repeat(self):
        table = TableConfiguration(
            path=[PathNode(name='foo', is_repeat=True), PathNode(name='bar', is_repeat=True)],
        )
        self.assertEqual(
            table._get_sub_documents(
                {
                    'foo': [
                        {
                            'bar': [
                                {'baz': 'a'},
                                {'baz': 'b'}
                            ],
                        },
                        {
                            'bar': [
                                {'baz': 'c'}
                            ],
                        },
                    ],
                },
                0
            ),
            [
                DocRow(row=(0, 0, 0), doc={'baz': 'a'}),
                DocRow(row=(0, 0, 1), doc={'baz': 'b'}),
                DocRow(row=(0, 1, 0), doc={'baz': 'c'}),
            ]
        )

    def test_single_iteration_repeat(self):
        table = TableConfiguration(
            path=[PathNode(name='group1', is_repeat=False), PathNode(name='repeat1', is_repeat=True)],
        )
        self.assertEqual(
            table._get_sub_documents(
                {
                    'group1': {
                        'repeat1': {
                            'baz': 'a'
                        },
                    }
                },
                0
            ),
            [
                DocRow(row=(0, 0), doc={'baz': 'a'}),
            ]
        )


class TableConfigurationGetRowsTest(SimpleTestCase):

    def test_simple(self):
        table_configuration = TableConfiguration(
            path=[],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=[PathNode(name='form'), PathNode(name='q3')],
                    ),
                    selected=True,
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=[PathNode(name='form'), PathNode(name='q1')],
                    ),
                    selected=True,
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=[PathNode(name='form'), PathNode(name='q2')],
                    ),
                    selected=False,
                ),
            ]
        )
        submission = {
            "form": {
                "q1": "foo",
                "q2": "bar",
                "q3": "baz"
            }
        }
        self.assertEqual(
            [row.data for row in table_configuration.get_rows(submission, 0)],
            [['baz', 'foo']]
        )

    def test_repeat(self):
        table_configuration = TableConfiguration(
            path=[PathNode(name="form", is_repeat=False), PathNode(name="repeat1", is_repeat=True)],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=[
                            PathNode(name="form"),
                            PathNode(name="repeat1", is_repeat=True),
                            PathNode(name="q1")
                        ],
                    ),
                    selected=True,
                ),
            ]
        )
        submission = {
            'form': {
                'repeat1': [
                    {'q1': 'foo'},
                    {'q1': 'bar'}
                ]
            }
        }
        self.assertEqual(
            [row.data for row in table_configuration.get_rows(submission, 0)],
            [ExportRow(['foo']).data, ExportRow(['bar']).data]
        )

    def test_double_repeat(self):
        table_configuration = TableConfiguration(
            path=[
                PathNode(name="form", is_repeat=False),
                PathNode(name="repeat1", is_repeat=True),
                PathNode(name="group1", is_repeat=False),
                PathNode(name="repeat2", is_repeat=True),
            ],
            columns=[
                RowNumberColumn(
                    selected=True
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=[
                            PathNode(name='form'),
                            PathNode(name='repeat1', is_repeat=True),
                            PathNode(name='group1'),
                            PathNode(name='repeat2', is_repeat=True),
                            PathNode(name='q1')
                        ],
                    ),
                    selected=True,
                ),
            ]
        )
        submission = {
            'form': {
                'repeat1': [
                    {
                        'group1': {
                            'repeat2': [
                                {'q1': 'foo'},
                                {'q1': 'bar'}
                            ]
                        }
                    },
                    {
                        'group1': {
                            'repeat2': [
                                {'q1': 'beep'},
                                {'q1': 'boop'}
                            ]
                        }
                    },
                ]
            }
        }
        self.assertEqual(
            [row.data for row in table_configuration.get_rows(submission, 0)],
            [
                ["0.0.0", 0, 0, 0, 'foo'],
                ["0.0.1", 0, 0, 1, 'bar'],
                ["0.1.0", 0, 1, 0, 'beep'],
                ["0.1.1", 0, 1, 1, 'boop']
            ]
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
        self.assertEqual(column.get_value(doc, [PathNode(name='form')], split_column=True), [1, None, "b d"])

    def test_ignore_extas(self):
        column = SplitExportColumn(
            item=MultipleChoiceItem(
                path=[PathNode(name='form'), PathNode(name='q1')],
                options=[Option(value='a'), Option(value='c')]
            ),
            ignore_unspecified_options=True
        )
        doc = {"q1": "a b d"}
        self.assertEqual(column.get_value(doc, [PathNode(name="form")], split_column=True), [1, None])

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
