import datetime
from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestDeliveryForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-dashboard_delivery_forms"

    def test_delivery_form(self):
        test_cases = (
            ('live', 0),
            ('still', 1),
            ('default', 0),
        )
        for xml_value, report_value in test_cases:
            self._test_data_source_results(
                'delivery_form_v10326',
                [
                    {
                        "doc_id": None,
                        "case_load_ccs_record0": "57d6bf6b-b33e-4e6b-bfa5-18f01b29e1ef",
                        "timeend": None,
                        "add": datetime.date(2018, 1, 7),
                        "where_born": 2,
                        "which_hospital": 2,
                        "breastfed_at_birth": 0,
                        "unscheduled_visit": 0,
                        "days_visit_late": 46,
                        "next_visit": datetime.date(2017, 10, 30),
                        "num_children_del": 1,
                        "still_birth": report_value,
                    }
                ],
                {
                    'still_live': xml_value
                }
            )
