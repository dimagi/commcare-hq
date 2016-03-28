from django.test import SimpleTestCase

from corehq.apps.export.models import ExportColumn
from corehq.apps.export.exceptions import ExportInvalidTransform


class TestExportColumn(SimpleTestCase):

    def test_invalid_transform_function(self):
        with self.assertRaises(ExportInvalidTransform):
            ExportColumn(transforms=['doesnotwork'])

    def test_valid_transform_function(self):
        col = ExportColumn(transforms=['deid_date', 'deid_id'])
        self.assertEqual(col.transforms, ['deid_date', 'deid_id'])
