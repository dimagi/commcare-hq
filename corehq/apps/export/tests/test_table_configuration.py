from django.test import SimpleTestCase

from corehq.apps.export.models import TableConfiguration, ExportColumn, \
    ScalarItem, ExportRow


class TableConfigurationGetRowsTest(SimpleTestCase):

    def test_simple(self):
        table_configuration = TableConfiguration(
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=['form', 'q3'],
                    )
                ),
                ExportColumn(
                    item=ScalarItem(
                        path=['form', 'q1'],
                    )
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
            [ExportRow(['baz', 'foo']).data]
        )

    def test_repeats(self):
        table_configuration = TableConfiguration(
            repeat_path=['form', 'repeat1'],
            columns=[
                ExportColumn(
                    item=ScalarItem(
                        path=['form', 'repeat1', 'q1'],
                    )
                ),
            ]
        )
        submission = {
            'form': {
                'repeat1': [
                    {'q1', 'foo'},
                    {'q1', 'bar'}
                ]
            }
        }
        self.assertEqual(
            table_configuration.get_rows(submission),
            [ExportRow(['foo']), ExportRow(['bar'])]
        )

    def test_split_columns(self):
        # TODO: It probably makes more sense to test columns independently...
        # I'm assuming they will have some sort of get_value(document) property
        table_configuration = TableConfiguration(
            repeat_path=['form'],
            columns=[
                SplitExportColumn(
                    item=MultipleChoiceItem(
                        path=['form', 'q1'],
                        options=['a', 'c']
                    ),
                    ignore_extras=False
                ),
                SplitExportColumn(
                    item=MultipleChoiceItem(
                        path=['form', 'q1'],
                        options=['a', 'c']
                    ),
                    ignore_extras=True
                ),
            ]
        )
        submission = {"form": {"q1": "a b d"}}
        self.assertEqual(
            [row.data for row in table_configuration.get_rows(submission)],
            [ExportRow([1, "", 1, "", "b d"]).data]
        )
