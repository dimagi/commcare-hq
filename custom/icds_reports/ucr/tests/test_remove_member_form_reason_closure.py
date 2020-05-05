import datetime
from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestChildDeliveryForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-remove_member"

    def test_delivery_form_single_child(self):

        self._test_data_source_results(
            'remove_member_form_v33188',
            [
                {
                    'doc_id': None,
                    'person_case_id': '9aa9fb7e-f90a-42db-8d17-415092531ad9',
                    'reason_closure': 'incorrect_reg'
                }
            ]
        )
