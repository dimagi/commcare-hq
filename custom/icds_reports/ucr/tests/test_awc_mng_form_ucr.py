from __future__ import absolute_import
from __future__ import unicode_literals

from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'supervisor')
class TestAWCMgtForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-awc_mgt_forms"

    def test_awc_visit_form_with_location_entered(self):
        self._test_data_source_results(
            'awc_visit_form_with_location',
            [{'count': 1,
              'awc_location_long': None,
              'awc_not_open_aww_not_available': 0,
              'user_id': 'cee18a35ce4fac591eba966c0d15d599',
              'doc_id': None,
              'awc_open': 1,
              'aww_present': 1,
              'month': None,
              'submitted_on': None,
              'awc_not_open_other': 0,
              'awc_location': None,
              'location_entered': 'center',
              'awc_not_open_holiday': 0,
              'awc_location_lat': None,
              'awc_not_open_unknown': 0,
              'location_id': 'qwe56poiuytr4xcvbnmkjfghwerffdaa',
              'awc_not_open_closed_early': 0}])

    def test_awc_visit_form_without_location_entered(self):
        self._test_data_source_results(
            'awc_visit_form_without_location',
            [{'count': 1,
              'awc_location_long': None,
              'awc_not_open_aww_not_available': 0,
              'user_id': 'cee18a35ce4fac591eba966c0d15d599',
              'doc_id': None,
              'awc_open': 1,
              'aww_present': 1,
              'month': None,
              'submitted_on': None,
              'awc_not_open_other': 0,
              'awc_location': None,
              'location_entered': '',
              'awc_not_open_holiday': 0,
              'awc_location_lat': None,
              'awc_not_open_unknown': 0,
              'location_id': 'qwe56poiuytr4xcvbnmkjfghwerffdaa',
              'awc_not_open_closed_early': 0}])
