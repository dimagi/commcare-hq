from django.test import SimpleTestCase

from corehq.apps.export.const import PROPERTY_TAG_ROW
from corehq.apps.export.models import ExportColumn
from corehq.apps.export.exceptions import ExportInvalidTransform
from corehq.apps.export.models.new import (
    RowNumberColumn,
    SystemExportItem,
    TableConfiguration,
    PathNode,
    CASE_HISTORY_TABLE,
    PARENT_CASE_TABLE,
    MAIN_TABLE,
)


class TestExportColumn(SimpleTestCase):

    def test_invalid_transform_function(self):
        with self.assertRaises(ExportInvalidTransform):
            ExportColumn(transforms=['doesnotwork'])

    def test_valid_transform_function(self):
        col = ExportColumn(transforms=['deid_date', 'deid_id'])
        self.assertEqual(col.transforms, ['deid_date', 'deid_id'])


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

    def test_instantiation(self):
        """
        The logic for creating RowNumberColumns has been error prone, so test
        a few scenarios here to ensure that everything works as expected
        """
        specs = [
            # table, sample doc, number of columns
            (MAIN_TABLE, {"form": {}}, 1),
            (CASE_HISTORY_TABLE, {"actions": [{}]}, 3),
            (PARENT_CASE_TABLE, {"indices": [{}]}, 3),
            (
                [
                    PathNode(name='form'),
                    PathNode(name='repeat1', is_repeat=True),
                    PathNode(name='repeat2', is_repeat=True),
                ],
                {
                    "form": {
                        'repeat1': [
                            {
                                'repeat2': [{}]
                            }
                        ]
                    }
                },
                4
            ),

        ]

        for table_path, sample_doc, expected_cols in specs:
            col = ExportColumn.create_default_from_export_item(
                table_path,
                SystemExportItem(
                    path=['number'],
                    label='number',
                    tag=PROPERTY_TAG_ROW,
                    is_advanced=False,
                ),
                {}
            )
            col.selected = True
            table = TableConfiguration(
                path=table_path,
                columns=[col]
            )
            self.assertEqual(len(table.get_headers()), expected_cols)
            self.assertEqual(len(table.get_rows(sample_doc, 0)[0].data), expected_cols)
