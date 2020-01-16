import datetime

from django.test import TestCase

from custom.icds_reports.const import GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
from custom.icds_reports.reports.governance_apis import get_home_visit_data, get_vhnd_data, get_state_names


class GovernanceApiTest(TestCase):

    def test_data_fetching_total_record_count_for_home_visit_api(self):
        """
        test to check the total count of records that are returned from the home visit api
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']
        data, count = get_home_visit_data(limit,
                                          2017, 5, order, query_filters)
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
                                          2017, 5, order, query_filters)
        expected_first_row = {
            'state': 'st1', 'district': 'd1', 'block': 'b1', 'sector': 's1', 'awc': 'a1', 'awc_id': 'a1',
            'month': datetime.date(2017, 5, 1), 'valid_visits': 0, 'expected_visits': 4,
        }
        self.assertEqual(data[0], expected_first_row)

    def test_data_fetching_with_start_for_home_visit_api(self):
        """
        test to check the first record that is returned from the home visit api with start parameter
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5, 'awc_id__gt': 'a1'}
        order = ['state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name']

        data, count = get_home_visit_data(limit,
                                          2017, 5, order, query_filters)
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
                                          2017, 6, order, query_filters)
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
                                          2017, 5, order, query_filters)
        expected_count = 26
        self.assertEqual(count, expected_count)

    def test_data_fetching_state_names_api(self):
        """
        test to check if state names are getting retreived from the api
        """
        data = get_state_names()
        expected_count = 6
        self.assertEqual(len(data), expected_count)

    def test_data_fetching_total_record_count_for_vhnds_visit_api(self):
        """
        test to check the total count of records that are returned from the vhnds api
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'state_id': 'st1'}
        order = ['awc_id', 'awc_code']
        data, count = get_vhnd_data(limit,
                                    2017, 5, order, query_filters)
        expected_count = 10
        self.assertEqual(count, expected_count)

    def test_data_fetching_without_start_for_vhnds_api(self):
        """
        test to check the first record that is returned from the vhnds api without start parameter
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'state_id': 'st1'}
        order = ['awc_id', 'awc_code']
        data, count = get_vhnd_data(limit,
                                    2017, 5, order, query_filters)
        expected_first_row = {
            "awc_id": "a41","awc_code": "a41",
            "month": datetime.date(2017, 5, 1), "vhsnd_conducted": "no", "vhsnd_date": "Data Not Entered",
            "anm_present": "no", "asha_present": "no", "any_child_immunized": "no",
            "anc_conducted": "no"
        }
        self.assertEqual(data[0], expected_first_row)

    def test_data_fetching_with_start_for_vhnds_api(self):
        """
        test to check the first record that is returned from the vhnds api with start parameter
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'state_id': 'st1', 'awc_id__gt': 'a41'}
        order = ['awc_id', 'awc_code']
        data, count = get_vhnd_data(limit, 2017, 5, order, query_filters)
        expected_first_row = {
            "awc_id": "a49","awc_code": "a49",
            "month": datetime.date(2017, 5, 1), "vhsnd_conducted": "no", "vhsnd_date": "Data Not Entered",
            "anm_present": "no", "asha_present": "no", "any_child_immunized": "no",
            "anc_conducted": "no"
        }
        self.assertEqual(data[0], expected_first_row)

    def test_data_fetching_total_record_count_for_no_records_for_vhnds_api(self):
        """
        test to check the no records are returned from the vhnds api
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'state_id': 'st1'}
        order = ['awc_id', 'awc_code']
        data, count = get_vhnd_data(limit, 2018, 6, order, query_filters)
        expected_count = 0
        self.assertEqual(count, expected_count)
        self.assertEqual(data, [])

    def test_data_fetching_retrieving_first_record_for_multiple_nhnds_per_month_per_awc(self):
        """
        test tp check if the first record is getting retrieved if there are multiple vhnds per month per awc
        """
        limit = GOVERNANCE_API_HOME_VISIT_RECORDS_PAGINATION
        query_filters = {'state_id': 'st1', 'awc_id__gt': 'a41'}
        order = ['awc_id', 'awc_code']
        data, count = get_vhnd_data(limit, 2017, 5, order, query_filters)
        expected_row = {
            "awc_id": "a49","awc_code": "a49",
            "month": datetime.date(2017, 5, 1), "vhsnd_conducted": "no",
            "vhsnd_date": "Data Not Entered", "anm_present": "no", "asha_present": "no",
            "any_child_immunized": "no", "anc_conducted": "no"
        }
        expected_counter = 1
        actual_row = None

        counter = 0
        for row in data:
            if row['awc'] == 'a49':
                actual_row = row
                counter += 1

        self.assertEqual(counter, expected_counter)
        self.assertEqual(actual_row, expected_row)



