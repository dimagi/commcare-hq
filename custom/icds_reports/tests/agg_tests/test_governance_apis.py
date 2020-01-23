import datetime

from django.test import TestCase

from custom.icds_reports.const import GOVERNANCE_API_RECORDS_PAGINATION
from custom.icds_reports.reports.governance_apis import get_home_visit_data, get_state_names, get_vhnd_data,\
    get_beneficiary_data

from custom.icds_reports.tasks import _agg_governance_dashboard
from datetime import date


class GovernanceApiTest(TestCase):

    def test_data_fetching_total_record_count_for_home_visit_api(self):
        """
        test to check the total count of records that are returned from the home visit api
        """
        limit = GOVERNANCE_API_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['awc_id']
        data, count = get_home_visit_data(limit,
                                          2017, 5, order, query_filters)
        expected_count = 55
        self.assertEqual(count, expected_count)

    def test_data_fetching_without_start_for_home_visit_api(self):
        """
        test to check the first record that is returned from the home visit api without start parameter
        """
        limit = GOVERNANCE_API_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['awc_id']
        data, count = get_home_visit_data(limit,
                                          2017, 5, order, query_filters)
        expected_first_row = {
            'awc_id': 'a1', 'awc_code': 'a1',
            'valid_visits': 0, 'expected_visits': 4,
        }
        self.assertEqual(data[0], expected_first_row)

    def test_data_fetching_with_start_for_home_visit_api(self):
        """
        test to check the first record that is returned from the home visit api with start parameter
        """
        limit = GOVERNANCE_API_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5, 'awc_id__gt': 'a1'}
        order = ['awc_id']

        data, count = get_home_visit_data(limit,
                                          2017, 5, order, query_filters)
        expected_first_row = {
            'awc_id': 'a10', 'awc_code': 'a10', 'valid_visits': 0, 'expected_visits': 2
        }
        self.assertEqual(data[0], expected_first_row)

    def test_data_fetching_total_record_count_for_no_records_for_home_visit_api(self):
        """
        test to check the no records are returned from the home visit api
        """
        limit = GOVERNANCE_API_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5}
        order = ['awc_id']
        data, count = get_home_visit_data(limit,
                                          2017, 6, order, query_filters)
        expected_count = 0
        self.assertEqual(count, expected_count)
        self.assertEqual(data, [])

    def test_data_fetching_total_record_count_with_state_id_for_home_visit_api(self):
        """
        test to check the total count of records that are returned from the home visit api
        """
        limit = GOVERNANCE_API_RECORDS_PAGINATION
        query_filters = {'aggregation_level': 5, 'state_id': 'st1'}
        order = ['awc_id']
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
        limit = GOVERNANCE_API_RECORDS_PAGINATION
        query_filters = {'state_id': 'st1', 'awc_launched': True}
        order = ['awc_id']
        data, count = get_vhnd_data(limit,
                                    2017, 5, order, query_filters)
        expected_count = 10
        self.assertEqual(count, expected_count)

    def test_data_fetching_without_start_for_vhnds_api(self):
        """
        test to check the first record that is returned from the vhnds api without start parameter
        """
        limit = GOVERNANCE_API_RECORDS_PAGINATION
        query_filters = {'state_id': 'st1', 'awc_launched': True}
        order = ['awc_id']
        data, count = get_vhnd_data(limit,
                                    2017, 5, order, query_filters)
        expected_first_row = {
            "awc_id": "a10", "awc_code": "a10", "vhsnd_conducted": "no", "vhsnd_date": "Data Not Entered",
            "anm_present": "no", "asha_present": "no", "any_child_immunized": "no",
            "anc_conducted": "no"
        }
        self.assertEqual(data[0], expected_first_row)

    def test_data_fetching_with_start_for_vhnds_api(self):
        """
        test to check the first record that is returned from the vhnds api with start parameter
        """
        limit = GOVERNANCE_API_RECORDS_PAGINATION
        query_filters = {'state_id': 'st1', 'awc_id__gt': 'a41', 'awc_launched': True}
        order = ['awc_id']
        data, count = get_vhnd_data(limit, 2017, 5, order, query_filters)
        expected_first_row = {
            "awc_id": "a43", "awc_code": "a43", "vhsnd_conducted": "no", "vhsnd_date": "Data Not Entered",
            "anm_present": "Data Not Entered", "asha_present": "Data Not Entered",
            "any_child_immunized": "Data Not Entered", "anc_conducted": "Data Not Entered"
        }
        self.assertEqual(data[0], expected_first_row)

    def test_data_fetching_total_record_count_for_no_records_for_vhnds_api(self):
        """
        test to check the no records are returned from the vhnds api
        """
        limit = GOVERNANCE_API_RECORDS_PAGINATION
        query_filters = {'state_id': 'st1', 'awc_launched': True}
        order = ['awc_id']
        data, count = get_vhnd_data(limit, 2018, 6, order, query_filters)
        expected_count = 0
        self.assertEqual(count, expected_count)
        self.assertEqual(data, [])

    def test_data_fetching_retrieving_first_record_for_multiple_nhnds_per_month_per_awc(self):
        """
        test tp check if the first record is getting retrieved if there are multiple vhnds per month per awc
        """
        limit = GOVERNANCE_API_RECORDS_PAGINATION
        query_filters = {'state_id': 'st1', 'awc_id__gt': 'a41', 'awc_launched': True}
        order = ['awc_id']
        data, count = get_vhnd_data(limit, 2017, 5, order, query_filters)
        expected_row = {
            "awc_id": "a49", "awc_code": "a49", "vhsnd_conducted": "yes",
            "vhsnd_date": datetime.date(2017, 5, 2), "anm_present": "no", "asha_present": "yes",
            "any_child_immunized": "yes", "anc_conducted": "no"
        }
        expected_counter = 1
        actual_row = None
        print(data)
        counter = 0
        for row in data:
            if row['awc_id'] == 'a49':
                actual_row = row
                counter += 1

        self.assertEqual(counter, expected_counter)
        self.assertEqual(actual_row, expected_row)

    def test_fetch_beneficiary_data(self):
        limit = 1
        _agg_governance_dashboard(date(2017, 5, 1))
        query_filters = {'state_id': 'st1'}
        order = ['awc_id']
        data, count = get_beneficiary_data(limit, 2017, 5, order, query_filters)
        self.assertEqual(len(data), limit)
        self.assertEqual([{'awc_id': 'a1', 'awc_code': 'a1', 'total_preg_benefit_till_date': 2,
                           'total_lact_benefit_till_date': 3, 'total_preg_reg_till_date': 2,
                           'total_lact_reg_till_date': 3, 'total_lact_benefit_in_month': 1,
                           'total_preg_benefit_in_month': 1, 'total_lact_reg_in_month': 1,
                           'total_preg_reg_in_month': 1,
                           'total_0_3_female_benefit_till_date': 'Data Not Entered',
                           'total_0_3_male_benefit_till_date': 'Data Not Entered',
                           'total_0_3_female_reg_till_date': 'Data Not Entered',
                           'total_0_3_male_reg_till_date': 'Data Not Entered',
                           'total_3_6_female_benefit_till_date': 'Data Not Entered',
                           'total_3_6_male_benefit_till_date': 'Data Not Entered',
                           'total_3_6_female_reg_till_date': 'Data Not Entered',
                           'total_3_6_male_reg_till_date': 'Data Not Entered',
                           'total_0_3_female_benefit_in_month': 'Data Not Entered',
                           'total_0_3_male_benefit_in_month': 'Data Not Entered',
                           'total_0_3_female_reg_in_month': 'Data Not Entered',
                           'total_0_3_male_reg_in_month': 'Data Not Entered',
                           'total_3_6_female_benefit_in_month': 'Data Not Entered',
                           'total_3_6_male_benefit_in_month': 'Data Not Entered',
                           'total_3_6_female_reg_in_month': 'Data Not Entered',
                           'total_3_6_male_reg_in_month': 'Data Not Entered'},
                          ], data)
