import datetime
from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestChildDeliveryForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-child_delivery_forms"

    def test_delivery_form_single_child(self):

        self._test_data_source_results(
            'delivery_form_single_kid',
            [
                {
                    "doc_id": None,
                    'child_health_case_id': '67134d8d-0ebf-447e-acf7-919f5327cfd3',
                    'delivery_nature': 'vaginal',
                    "add": datetime.date(2019, 12, 3),
                    "edd": datetime.date(2019, 12, 3),
                    'birth_weight_kg': None,
                    'still_live_birth': 'live',
                    'submitted_on': None,
                    'lbw_F_migrant_birth_count': 0,
                    'lbw_F_resident_birth_count': 0,
                    'lbw_M_migrant_birth_count': 0,
                    'lbw_M_resident_birth_count': 0,
                    'live_F_migrant_birth_count': 0,
                    'live_F_resident_birth_count': 1,
                    'live_M_migrant_birth_count': 0,
                    'live_M_resident_birth_count': 0,
                    'mother_resident_status': 'yes',
                    'repeat_iteration': 0,
                    'sex': 'F',
                    'still_F_migrant_birth_count': 0,
                    'still_F_resident_birth_count': 0,
                    'still_M_migrant_birth_count': 0,
                    'still_M_resident_birth_count': 0,
                    'weighed_F_migrant_birth_count': 0,
                    'weighed_F_resident_birth_count': 0,
                    'weighed_M_migrant_birth_count': 0,
                    'weighed_M_resident_birth_count': 0
                }
            ]
        )

    def test_delivery_form_multiple_child(self):

        self._test_data_source_results(
            'delivery_form_multiple_kids',
            [
                {
                    'add': datetime.date(2020, 4, 9),
                    "edd": datetime.date(2020, 4, 9),
                    'birth_weight_kg': None,
                    'child_health_case_id': 'fc3683ef-94d8-4d0f-a681-148cc7d3b659',
                    'delivery_nature': 'vaginal',
                    'doc_id': None,
                    'lbw_F_migrant_birth_count': 0,
                    'lbw_F_resident_birth_count': 0,
                    'lbw_M_migrant_birth_count': 0,
                    'lbw_M_resident_birth_count': 0,
                    'live_F_migrant_birth_count': 0,
                    'live_F_resident_birth_count': 0,
                    'live_M_migrant_birth_count': 1,
                    'live_M_resident_birth_count': 0,
                    'mother_resident_status': 'no',
                    'repeat_iteration': 0,
                    'sex': 'M',
                    'still_F_migrant_birth_count': 0,
                    'still_F_resident_birth_count': 0,
                    'still_M_migrant_birth_count': 0,
                    'still_M_resident_birth_count': 0,
                    'still_live_birth': 'live',
                    'submitted_on': None,
                    'weighed_F_migrant_birth_count': 0,
                    'weighed_F_resident_birth_count': 0,
                    'weighed_M_migrant_birth_count': 0,
                    'weighed_M_resident_birth_count': 0},
                {
                    'add': datetime.date(2020, 4, 9),
                    'edd': datetime.date(2020, 4, 9),
                    'birth_weight_kg': None,
                    'child_health_case_id': 'dc0eec14-565e-44cb-a82f-b99dc63a023c',
                    'delivery_nature': 'vaginal',
                    'doc_id': None,
                    'lbw_F_migrant_birth_count': 0,
                    'lbw_F_resident_birth_count': 0,
                    'lbw_M_migrant_birth_count': 0,
                    'lbw_M_resident_birth_count': 0,
                    'live_F_migrant_birth_count': 1,
                    'live_F_resident_birth_count': 0,
                    'live_M_migrant_birth_count': 0,
                    'live_M_resident_birth_count': 0,
                    'mother_resident_status': 'no',
                    'repeat_iteration': 1,
                    'sex': 'F',
                    'still_F_migrant_birth_count': 0,
                    'still_F_resident_birth_count': 0,
                    'still_M_migrant_birth_count': 0,
                    'still_M_resident_birth_count': 0,
                    'still_live_birth': 'live',
                    'submitted_on': None,
                    'weighed_F_migrant_birth_count': 0,
                    'weighed_F_resident_birth_count': 0,
                    'weighed_M_migrant_birth_count': 0,
                    'weighed_M_resident_birth_count': 0
                }
            ]
        )
