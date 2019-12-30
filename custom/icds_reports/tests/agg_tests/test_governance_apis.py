import datetime

from django.test import TestCase

from custom.icds_reports.const import GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
from custom.icds_reports.reports.governance_apis import get_home_visit_data
from custom.icds_reports.utils import india_now


class GovernanceApiTest(TestCase):

    def test_data_fetching_total_record_count_for_home_visit_api(self):
        """
        test to check the total count of records that are returned from the home visit api
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        data = get_home_visit_data(0, limit,
                                   2017, 5, order, query_filters)
        expected_count = 55
        self.assertEqual(data['filter_params']['count'], expected_count)

    def test_data_fetching_without_start_for_home_visit_api(self):
        """
        test to check the first record that is returned from the home visit api without start parameter
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        data = get_home_visit_data(0, limit,
                                   2017, 5, order, query_filters)
        expected_first_row = {
            'state': 'st1', 'district': 'd1', 'block': 'b1', 'sector': 's1', 'awc': 'a1',
            'month': datetime.date(2017, 5, 1), 'valid_visits': 0, 'expected_visits': 4,
        }
        self.assertEqual(data['data'][0], expected_first_row)

    def test_data_fetching_with_start_for_home_visit_api(self):
        """
        test to check the first record that is returned from the home visit api with start parameter
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        data = get_home_visit_data(1, limit,
                                   2017, 5, order, query_filters)
        expected_first_row = {
            'state': 'st1', 'district': 'd1', 'block': 'b1', 'sector': 's1', 'awc': 'a17',
            'month': datetime.date(2017, 5, 1), 'valid_visits': 0, 'expected_visits': 3
        }
        self.assertEqual(data['data'][0], expected_first_row)

    def test_filter_param_in_response_for_home_visit_api(self):
        """
        test to check the filter params are returned from the home visit api with start parameter
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        data = get_home_visit_data(1, limit,
                                   2017, 5, order, query_filters)
        expected = {
            'start': 1,
            'month': 5,
            'year': 2017,
            'count': 55,
            'timestamp': india_now()
        }
        self.assertEqual(data['filter_params'], expected)

    def test_data_fetching_total_record_count_for_no_records_for_home_visit_api(self):
        """
        test to check the no records are returned from the home visit api
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        data = get_home_visit_data(0, limit,
                                   2017, 6, order, query_filters)
        expected_count = 0
        self.assertEqual(data['filter_params']['count'], expected_count)
        self.assertEqual(data['data'], [])

    def test_data_fetching_total_record_count_with_state_id_for_home_visit_api(self):
        """
        test to check the total count of records that are returned from the home visit api
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5, 'state_id': 'st1'}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        data = get_home_visit_data(0, limit,
                                   2017, 5, order, query_filters)
        expected_count = 26
        self.assertEqual(data['filter_params']['count'], expected_count)
