from __future__ import absolute_import
from __future__ import unicode_literals

from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'supervisor')
class TestAWCMgtForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-ls_home_visit_forms_filled"

    def test_awc_visit_form_with_location_entered(self):
        self._test_data_source_results(
            'beneficiary_form_with_type_of_visit',
            [{'user_id': 'cee18a35ce4fac591eba966c0d15d599',
              'location_id': 'qwe56poiuytr4xcvbnmkjfghwerffdaa',
              'doc_id': None,
              'visit_type_entered': 'vhnd_day',
              'home_visit_count': 1,
              'submitted_on': None}])

    def test_awc_visit_form_without_location_entered(self):
        self._test_data_source_results(
            'beneficiary_form_without_type_of_visit',
            [{'user_id': 'cee18a35ce4fac591eba966c0d15d599',
              'location_id': 'qwe56poiuytr4xcvbnmkjfghwerffdaa',
              'doc_id': None,
              'visit_type_entered': '',
              'home_visit_count': 1,
              'submitted_on': None}])
