from __future__ import absolute_import
from __future__ import unicode_literals

from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestTHRForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-dashboard_thr_forms"

    def test_with_child_form(self):
        self._test_data_source_results(
            'thr_form_with_child',
            [{
                "doc_id": None,
                "repeat_iteration": 0,
                "timeend": None,
                "ccs_record_case_id": "ef8a946d-3f6a-4715-b743-68d55b86a230",
                "child_health_case_id": "cccd8d00-851c-4524-ab12-811ac98d1fe9",
                "days_ration_given_child": 22,
                "days_ration_given_mother": None
            }])

    def test_without_child_form(self):
        self._test_data_source_results(
            'thr_form_without_child',
            [{
                "doc_id": None,
                "repeat_iteration": 0,
                "timeend": None,
                "ccs_record_case_id": "ecf7d5cc-123d-41d2-a0d7-edf722895d13",
                "child_health_case_id": None,
                "days_ration_given_child": None,
                "days_ration_given_mother": 22
            }])
