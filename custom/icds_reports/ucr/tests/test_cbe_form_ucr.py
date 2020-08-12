import datetime

from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestcbeForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-cbe_form"

    def test_cbe_form_date(self):
        self._test_data_source_results(
            'cbe_form', [{
                'submitted_on': datetime.datetime(2018, 12, 10, 14, 38, 53, 603000),
                'doc_id': None,
                'date_cbe_organise': datetime.date(2018, 12, 10),
                'count_other_beneficiaries': 25,
                'count_targeted_beneficiaries': 1,
                'theme_cbe': 'third_fourth_month_of_pregnancy'
            }
            ])

    def test_cbe_coming_of_age(self):
        self._test_data_source_results(
            'cbe_form_coming_of_age', [{
                'submitted_on': datetime.datetime(2019, 11, 21, 10, 7, 44, 951000),
                'doc_id': None,
                'date_cbe_organise': datetime.date(2019, 11, 21),
                'count_other_beneficiaries': 93,
                'count_targeted_beneficiaries': 2,
                'theme_cbe': 'coming_of_age'
            }
            ])

    def test_cbe_suposhan_diwas(self):
        self._test_data_source_results(
            'cbe_form_suposhan_diwas', [{
                'submitted_on': datetime.datetime(2019, 10, 11, 12, 5, 27, 795000),
                'doc_id': None,
                'date_cbe_organise': datetime.date(2019, 10, 11),
                'count_targeted_beneficiaries': 8,
                'count_other_beneficiaries': None,
                'theme_cbe': 'suposhan_diwas'
            }
            ])

    def test_cbe_annaprasan_diwas(self):
        self._test_data_source_results(
            'cbe_form_annaprasan_diwas', [{
                'submitted_on': datetime.datetime(2019, 10, 11, 9, 8, 10, 547000),
                'doc_id': None,
                'date_cbe_organise': datetime.date(2019, 10, 11),
                'count_other_beneficiaries': 9,
                'count_targeted_beneficiaries': 1,
                'theme_cbe': 'annaprasan_diwas'
            }
            ])

    def test_cbe_public_health_message(self):
        self._test_data_source_results(
            'cbe_form_public_health_message', [{
                'submitted_on': datetime.datetime(2019, 8, 13, 8, 23, 4, 886000),
                'doc_id': None,
                'date_cbe_organise': datetime.date(2018, 8, 13),
                'count_other_beneficiaries': 4,
                'count_targeted_beneficiaries': 107,
                'theme_cbe': 'public_health_message'

            }
            ])
