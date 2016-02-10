from django.test import SimpleTestCase

from corehq.apps.export.models import TableConfiguration, ExportColumn, \
    ScalarItem, ExportRow
from corehq.apps.export.models.new import SplitExportColumn, MultipleChoiceItem, \
    Option


class TableConfigurationGetRowsTest(SimpleTestCase):

    def test_simple(self):
        table_configuration = TableConfiguration(
            path=[],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=['form', 'q3'],
                    ),
                    selected=True,
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=['form', 'q1'],
                    ),
                    selected=True,
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=['form', 'q2'],
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
            [row.data for row in table_configuration.get_rows(submission)],
            [['baz', 'foo']]
        )

    def test_repeat(self):
        table_configuration = TableConfiguration(
            path=['form', 'repeat1'],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=['form', 'repeat1', 'q1'],
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
            [row.data for row in table_configuration.get_rows(submission)],
            [ExportRow(['foo']).data, ExportRow(['bar']).data]
        )

    def test_double_repeat(self):
        table_configuration = TableConfiguration(
            path=['form', 'repeat1', 'group1', 'repeat2'],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=['form', 'repeat1', 'group1', 'repeat2', 'q1'],
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
            [row.data for row in table_configuration.get_rows(submission)],
            [['foo'], ['bar'], ['beep'], ['boop']]
        )


class SplitColumnTest(SimpleTestCase):

    def test_get_value(self):
        column = SplitExportColumn(
            item=MultipleChoiceItem(
                path=['form', 'q1'],
                options=[Option(value='a'), Option(value='c')]
            ),
            ignore_extras=False
        )
        doc = {"q1": "a b d"}
        self.assertEqual(column.get_value(doc, ['form']), [1, None, "b d"])

    def test_ignore_extas(self):
        column = SplitExportColumn(
            item=MultipleChoiceItem(
                path=['form', 'q1'],
                options=[Option(value='a'), Option(value='c')]
            ),
            ignore_extras=True
        )
        doc = {"q1": "a b d"}
        self.assertEqual(column.get_value(doc, ["form"]), [1, None])

    def test_basic_get_headers(self):
        column = SplitExportColumn(
            label="Fruit",
            item=MultipleChoiceItem(
                options=[Option(value='Apple'), Option(value='Banana')]
            ),
            ignore_extras=True
        )
        self.assertEqual(column.get_headers(), ["Fruit | Apple", "Fruit | Banana"])

    def test_get_headers_with_template_string(self):
        column = SplitExportColumn(
            label="Fruit - {option}",
            item=MultipleChoiceItem(
                options=[Option(value='Apple'), Option(value='Banana')]
            ),
            ignore_extras=True
        )
        self.assertEqual(column.get_headers(), ["Fruit - Apple", "Fruit - Banana"])

    def test_get_headers_with_extras(self):
        column = SplitExportColumn(
            label="Fruit - {option}",
            item=MultipleChoiceItem(
                options=[Option(value='Apple'), Option(value='Banana')]
            ),
            ignore_extras=False
        )
        self.assertEqual(column.get_headers(), ["Fruit - Apple", "Fruit - Banana", "Fruit - extra"])

    def test_get_column(self):
        table_configuration = TableConfiguration(
            path=['form', 'repeat1'],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=['form', 'repeat1', 'q1'],
                    )
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=['form', 'repeat1', 'q2'],
                    )
                ),
            ]
        )

        column = table_configuration.get_column(['form', 'repeat1', 'q1'])
        self.assertEqual(column.item.path, ['form', 'repeat1', 'q1'])

        column = table_configuration.get_column(['form', 'repeat1', 'DoesNotExist'])
        self.assertIsNone(column)
