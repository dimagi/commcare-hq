import datetime
from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestCounselling_guidance_form(BaseFormsTest):
    ucr_name = "static-icds-cas-dashboard_counselling_and_guidance_forms"

    def test_counselling_and_guidance_form(self):
        self._test_data_source_results(
            'static_dashboard_counselling_and_guidance_forms',
            [{
                'admitted_in_school': None,
                "doc_id": None,
                "timeend": datetime.datetime(2019, 12, 9, 8, 23, 52, 511000),
                'out_of_school': 'yes',
                'person_case_id': 'dda684cc-f260-4a0e-b608-f22aca3bf467',
                're_out_of_school': None,
              }
             ])
