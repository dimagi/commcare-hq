import datetime

from django.test import TestCase

from custom.icds_reports.const import GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
from custom.icds_reports.reports.governance_apis import get_home_visit_data
from custom.icds_reports.utils import india_now
from custom.icds_reports.views import GovernanceAPIView

class GovernanceApiTest(TestCase):

    def test_data_fetching_total_record_count_for_home_visit_api(self):
        """
        test to check the total count of records that are returned from the home visit api
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        data, count = get_home_visit_data(limit,
                                          2017, 5, order, query_filters, {})
        expected_count = 55
        self.assertEqual(count, expected_count)

    def test_data_fetching_without_start_for_home_visit_api(self):
        """
        test to check the first record that is returned from the home visit api without start parameter
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        data, count = get_home_visit_data(limit,
                                          2017, 5, order, query_filters, {})
        expected_first_row = {
            'state': 'st1', 'district': 'd1', 'block': 'b1', 'sector': 's1', 'awc': 'a1', 'awc_id':'a1',
            'month': datetime.date(2017, 5, 1), 'valid_visits': 0, 'expected_visits': 4,
        }
        self.assertEqual(data[0], expected_first_row)

    def test_data_fetching_with_start_for_home_visit_api(self):
        """
        test to check the first record that is returned from the home visit api with start parameter
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        last_awc_id = 'a1'
        awc_details = GovernanceAPIView.get_awc_details(last_awc_id)
        inclusion_filter, exclusion_filter = GovernanceAPIView.prepare_pagination_filters(awc_details)

        query_filters.update(inclusion_filter)

        data, count = get_home_visit_data(limit,
                                          2017, 5, order, query_filters, exclusion_filter)
        expected_first_row = {
            'state': 'st1', 'district': 'd1', 'block': 'b1', 'sector': 's1', 'awc': 'a17', 'awc_id': 'a17',
            'month': datetime.date(2017, 5, 1), 'valid_visits': 0, 'expected_visits': 3
        }
        self.assertEqual(data[0], expected_first_row)

    def test_data_fetching_total_record_count_for_no_records_for_home_visit_api(self):
        """
        test to check the no records are returned from the home visit api
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        data, count = get_home_visit_data(limit,
                                          2017, 6, order, query_filters, {})
        expected_count = 0
        self.assertEqual(count, expected_count)
        self.assertEqual(data, [])

    def test_data_fetching_total_record_count_with_state_id_for_home_visit_api(self):
        """
        test to check the total count of records that are returned from the home visit api
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5, 'state_id': 'st1'}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        data, count = get_home_visit_data(limit,
                                          2017, 5, order, query_filters, {})
        expected_count = 26
        self.assertEqual(count, expected_count)
