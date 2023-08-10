import datetime

from django.test import SimpleTestCase

import sqlalchemy

from corehq.apps.userreports.util import get_indicator_adapter

from ..sql import get_indicator_table
from ..views import _get_db_query_from_user_params, process_url_params
from .test_data_source_config import get_sample_data_source


class ParameterTest(SimpleTestCase):

    def setUp(self):
        self.config = get_sample_data_source()
        self.columns = get_indicator_table(self.config, sqlalchemy.MetaData()).columns

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

    def test_pagination_params_specified(self):
        params = process_url_params({'offset': 1, 'limit': 2}, self.columns)
        indicator_adapter = get_indicator_adapter(self.config, load_source='export_data_source')
        query = _get_db_query_from_user_params(indicator_adapter, params)
        self.assertEqual(params.offset, 1)
        self.assertEqual(query._offset, 1)
        self.assertEqual(params.limit, 2)
        self.assertEqual(query._limit, 2)

    def test_pagination_params_not_specified(self):
        params = process_url_params({'count-range': '10..30'}, self.columns)
        indicator_adapter = get_indicator_adapter(self.config, load_source='export_data_source')
        query = _get_db_query_from_user_params(indicator_adapter.get_query_object(), params)
        self.assertEqual(params.offset, None)
        self.assertEqual(query._offset, None)
        self.assertEqual(params.limit, None)
        self.assertEqual(query._limit, None)
