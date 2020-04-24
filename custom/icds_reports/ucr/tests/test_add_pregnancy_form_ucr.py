from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestAddPregnancyForm(BaseFormsTest):
    ucr_name = "static-icds-cas-static-dashboard_add_pregnancy_form"

    def test_delivery_form(self):
        self._test_data_source_results(
            'add_preg_form',
            [
                {
                    "doc_id": None,
                    "case_load_ccs_record0": "e79ae232-f1e8-4bc1-82b5-794367f2a79c",
                    "timeend": None,
                    "last_preg": 2
                }
            ]
        )
