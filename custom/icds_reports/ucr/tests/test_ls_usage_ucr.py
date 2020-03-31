import datetime
from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'supervisor')
class TestLsUsage(BaseFormsTest):
    ucr_name = "static-icds-cas-static-ls_usage_forms"

    def test_vhnd_form_inclusion(self):
        self._test_data_source_results(
            'ls_vhnd_observation_form', [{
                'timeend': datetime.datetime(2018, 8, 24, 8, 6, 40, 712000),
                'doc_id': None
            }
            ])

    def test_awc_mngt_form_inclusion(self):
        self._test_data_source_results(
            'awc_visit_form_with_location', [{
                'timeend': datetime.datetime(2018, 11, 6, 15, 24, 34, 784000),
                'doc_id': None
            }
            ])

    def test_ls_home_visit_form_inclusion(self):
        self._test_data_source_results(
            'ls_home_visits', [{
                'timeend': datetime.datetime(2019, 3, 27, 7, 15, 37, 183000),
                'doc_id': None
            }
            ])
