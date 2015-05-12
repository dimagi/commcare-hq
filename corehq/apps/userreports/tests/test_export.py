from django.test import SimpleTestCase

from .test_data_source_config import get_sample_data_source
from ..sql import get_indicator_table
from ..views import process_url_params, ExportParameters


class ParameterTest(SimpleTestCase):
    def setUp(self):
        config = get_sample_data_source()
        self.table = get_indicator_table(config)

    def test_no_parameters(self):
        params = process_url_params({}, self.table.columns)
        self.assertEqual(params.format, 'unzipped-csv')
        self.assertEqual(params.keyword_filters, {})
        self.assertEqual(params.sql_filters, [])

    def test_last30(self):
        params = process_url_params({'date': 'last30'}, self.table.columns)
        date_column = self.table.columns['date']
        result_filter = params.sql_filters[0]
        desired_filter = date_column.between('2014-02-02', '2014-10-02')
        self.assertTrue(result_filter.compare(desired_filter))
