from django.test import SimpleTestCase

from corehq.apps.export.export import _write_export_file
from corehq.apps.export.models import TableConfiguration, ExportColumn, \
    ScalarItem
from corehq.apps.export.models.new import ExportInstance


class WriteExportFileTest(SimpleTestCase):

    def test_simple(self):
        export_instance = ExportInstance(
            tables=[
                TableConfiguration(
                    name="My table",
                    columns=[
                        ExportColumn(
                            label="Q3",
                            item=ScalarItem(
                                path=['form', 'q3'],
                            )
                        ),
                        ExportColumn(
                            label="Q1",
                            item=ScalarItem(
                                path=['form', 'q1'],
                            )
                        ),
                    ]
                )
            ]
        )
        docs = [
            {
                "form": {
                    "q1": "foo",
                    "q2": "bar",
                    "q3": "baz"
                }
            },
            {
                "form": {
                    "q1": "bip",
                    "q2": "boop",
                    "q3": "bop"
                }
            },
        ]
        self.assertEqual(
            _write_export_file(export_instance, docs),
            [
                {
                    u'headers': [u'Q3', u'Q1'],
                    u'rows': [[u'baz', u'foo'], [u'bop', u'bip']],
                    u'table_name': u'My table'
                }
            ]
        )


class ExportDocRetreivalTest(SimpleTestCase):

    def test_export_es_query(self):
        pass
