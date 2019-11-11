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
                'submitted_on': None,
                'doc_id': None,
                'location_id': 'qwe56poiuytr4xcvbnmkjfghwerffdaa',
                'count': 1
            }
            ])

    def test_awc_mngt_form_inclusion(self):
        self._test_data_source_results(
            'awc_visit_form_with_location', [{
                'submitted_on': None,
                'doc_id': None,
                'location_id': 'qwe56poiuytr4xcvbnmkjfghwerffdaa',
                'count': 1
            }
            ])

    def test_ls_home_visit_form_inclusion(self):
        self._test_data_source_results(
            'ls_home_visits', [{
                'submitted_on': None,
                'doc_id': None,
                'location_id': 'qwe56poiuytr4xcvbnmkjfghwerffdaa',
                'count': 1
            }
            ])

