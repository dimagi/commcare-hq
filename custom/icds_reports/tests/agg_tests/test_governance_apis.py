import datetime

from django.test import TestCase


from custom.icds_reports.const import CAS_API_PAGE_SIZE
from custom.icds_reports.reports.governance_apis import get_home_visit_data, get_state_names, get_vhnd_data,\
    get_beneficiary_data, get_cbe_data

from custom.icds_reports.tasks import _agg_governance_dashboard
from datetime import date


class GovernanceApiTest(TestCase):

    def setUp(self):
        _agg_governance_dashboard(date(2017, 5, 1))

    def test_data_fetching_total_record_count_for_home_visit_api(self):
        """
        test to check the total count of records that are returned from the home visit api
        """
        limit = CAS_API_PAGE_SIZE
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
        limit = CAS_API_PAGE_SIZE
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
        limit = CAS_API_PAGE_SIZE
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
        limit = CAS_API_PAGE_SIZE
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
        limit = CAS_API_PAGE_SIZE
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
        limit = CAS_API_PAGE_SIZE
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
        limit = CAS_API_PAGE_SIZE
        query_filters = {'state_id': 'st1', 'awc_launched': True}
        order = ['awc_id']
        data, count = get_vhnd_data(limit,
                                    2017, 5, order, query_filters)
        expected_first_row = {
            "awc_id": "a10", "awc_code": "a10", "vhsnd_conducted": "no", "vhsnd_date": None,
            "anm_present": None, "asha_present": None,
            "children_immunized": None, "anc_conducted": None
        }
        self.assertEqual(data[0], expected_first_row)

    def test_data_fetching_with_start_for_vhnds_api(self):
        """
        test to check the first record that is returned from the vhnds api with start parameter
        """
        limit = CAS_API_PAGE_SIZE
        query_filters = {'state_id': 'st1', 'awc_id__gt': 'a41', 'awc_launched': True}
        order = ['awc_id']
        data, count = get_vhnd_data(limit, 2017, 5, order, query_filters)
        expected_first_row = {
            "awc_id": "a43", "awc_code": "a43", "vhsnd_conducted": "no", "vhsnd_date": None,
            "anm_present": None, "asha_present": None,
            "children_immunized": None, "anc_conducted": None
        }
        self.assertEqual(data[0], expected_first_row)

    def test_data_fetching_total_record_count_for_no_records_for_vhnds_api(self):
        """
        test to check the no records are returned from the vhnds api
        """
        limit = CAS_API_PAGE_SIZE
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
        limit = CAS_API_PAGE_SIZE
        query_filters = {'state_id': 'st2', 'awc_launched': True}
        order = ['awc_id']
        data, count = get_vhnd_data(limit, 2017, 5, order, query_filters)
        expected_row = {
            "awc_id": "a22", "awc_code": "a22", "vhsnd_conducted": "yes",
            "vhsnd_date": datetime.date(2017, 5, 16), "anm_present": "yes", "asha_present": "yes",
            "children_immunized": "yes", "anc_conducted": "yes"
        }
        expected_counter = 1
        actual_row = None
        counter = 0
        for row in data:
            if row['awc_id'] == 'a22':
                actual_row = row
                counter += 1

        self.assertEqual(counter, expected_counter)
        self.assertEqual(actual_row, expected_row)

    def test_fetch_beneficiary_data(self):
        limit = 1
        query_filters = {'state_id': 'st1'}
        order = ['awc_id']
        data, count = get_beneficiary_data(limit, 2017, 5, order, query_filters)
        self.assertEqual(len(data), limit)
        self.assertEqual([{'awc_id': 'a1', 'awc_code': 'a1', 'total_preg_benefit_till_date': 2,
                           'total_lact_benefit_till_date': 3, 'total_preg_reg_till_date': 2,
                           'total_lact_reg_till_date': 3, 'total_lact_benefit_in_month': 1,
                           'total_preg_benefit_in_month': 1, 'total_lact_reg_in_month': 1,
                           'total_preg_reg_in_month': 1,
                           'total_0_3_female_benefit_till_date': None,
                           'total_0_3_male_benefit_till_date': None,
                           'total_0_3_female_reg_till_date': None,
                           'total_0_3_male_reg_till_date': None,
                           'total_3_6_female_benefit_till_date': None,
                           'total_3_6_male_benefit_till_date': None,
                           'total_3_6_female_reg_till_date': None,
                           'total_3_6_male_reg_till_date': None,
                           'total_0_3_female_benefit_in_month': None,
                           'total_0_3_male_benefit_in_month': None,
                           'total_0_3_female_reg_in_month': None,
                           'total_0_3_male_reg_in_month': None,
                           'total_3_6_female_benefit_in_month': None,
                           'total_3_6_male_benefit_in_month': None,
                           'total_3_6_female_reg_in_month': None,
                           'total_3_6_male_reg_in_month': None},
                          ], data)

    def test_fetch_cbe_data(self):
        limit = 1
        _agg_governance_dashboard(date(2017, 5, 1))
        query_filters = {'state_id': 'st2'}
        order = ['awc_id']
        data, count = get_cbe_data(limit, 2017, 5, order, query_filters)
        self.assertEqual(len(data), limit)
        self.assertEqual([{'awc_code': 'a13',
                           'awc_id': 'a13',
                           'cbe_conducted_1': 'yes',
                           'cbe_conducted_2': 'yes',
                           'cbe_date_1': datetime.date(2017, 5, 2),
                           'cbe_date_2': datetime.date(2017, 5, 14),
                           'cbe_type_1': 'annaprasan_diwas',
                           'cbe_type_2': 'suposhan_diwas',
                           'num_other_beneficiaries_1': 1,
                           'num_other_beneficiaries_2': 0,
                           'num_target_beneficiaries_1': 12,
                           'num_target_beneficiaries_2': 8}
                          ], data)
