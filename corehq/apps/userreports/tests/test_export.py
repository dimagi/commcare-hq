from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
import sqlalchemy

from django.test import SimpleTestCase

from .test_data_source_config import get_sample_data_source
from ..sql import get_indicator_table
from ..views import process_url_params


class ParameterTest(SimpleTestCase):

    def setUp(self):
        config = get_sample_data_source()
        self.columns = get_indicator_table(config, sqlalchemy.MetaData()).columns

    def test_no_parameters(self):
        params = process_url_params({}, self.columns)
        self.assertEqual(params.format, 'unzipped-csv')
        self.assertEqual(params.keyword_filters, {})
        self.assertEqual(params.sql_filters, [])

    def test_lastndays(self):
        params = process_url_params({'date-lastndays': '30'}, self.columns)
        result_filter = params.sql_filters[0]

        end = datetime.date.today()
        start = end - datetime.timedelta(days=30)
        date_column = self.columns['date']
        desired_filter = date_column.between(start, end)

        self.assertTrue(result_filter.compare(desired_filter))

    def test_range_filter(self):
        params = process_url_params({'count-range': '10..30'}, self.columns)
        result_filter = params.sql_filters[0]

        count_column = self.columns['count']
        desired_filter = count_column.between('10', '30')

        self.assertTrue(result_filter.compare(desired_filter))
