import datetime

from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestAvailingServiceForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-availing_service_form"

    def test_availing_service_form(self):
        self._test_data_source_results(
            'availing_service_form_v32409',
            [{
                "doc_id": None,
                "is_registered": 1,
                "person_case_id": "5e4447eb-6ec3-40d9-9c8d-9ca775dfc0bc",
                "timeend": datetime.datetime(2020, 2, 28, 7, 51, 16, 926000)
            }])
