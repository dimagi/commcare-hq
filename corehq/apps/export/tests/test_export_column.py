from django.test import SimpleTestCase

from corehq.apps.export.models import ExportColumn
from corehq.apps.export.exceptions import ExportInvalidTransform
from corehq.apps.export.models.new import (
    RowNumberColumn,
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
