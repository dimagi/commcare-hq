from django.test import SimpleTestCase as TestCase
from corehq.apps.export.custom_export_helpers import CustomExportHelper
from corehq.apps.export.exceptions import BadExportConfiguration
from couchexport.models import Format


class UnzippedCsvTest(TestCase):
    def test_one_table(self):
        CustomExportHelper.check_export(Format.UNZIPPED_CSV, 1)

    def test_two_tables(self):
        with self.assertRaises(BadExportConfiguration):
            CustomExportHelper.check_export(Format.UNZIPPED_CSV, 2)

    def test_zipped_format(self):
        CustomExportHelper.check_export(Format.CSV, 2)
