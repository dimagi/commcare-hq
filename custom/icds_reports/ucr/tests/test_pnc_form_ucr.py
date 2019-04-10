from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import date

from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestPNCForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-postnatal_care_forms"

    def test_ebf_form(self):
        self._test_data_source_results(
            'ebf_form_v10326',
            [{
                "doc_id": None,
                "repeat_iteration": 0,
                "timeend": None,
                "ccs_record_case_id": "d53c940c-3bf3-44f7-97a1-f43fcbe74359",
                "child_health_case_id": "03f39da4-8ea3-4108-b8a8-1b58fdb4a698",
                "counsel_adequate_bf": None,
                "counsel_breast": None,
                "counsel_exclusive_bf": None,
                "counsel_increase_food_bf": None,
                "counsel_methods": None,
                "counsel_only_milk": 1,
                "skin_to_skin": None,
                "is_ebf": 1,
                "water_or_milk": 0,
                "other_milk_to_child": None,
                "tea_other": 0,
                "eating": 0,
                "not_breastfeeding": None,
                "unscheduled_visit": 0,
                "days_visit_late": 28,
                "next_visit": date(2017, 6, 17)
            }])

    def test_pnc_form(self):
        self._test_data_source_results(
            'pnc_form_v10326',
            [{
                "doc_id": None,
                "repeat_iteration": 0,
                "timeend": None,
                "ccs_record_case_id": "081cc405-5598-430f-ac8f-39cc4a1fdb30",
                "child_health_case_id": "252d8e20-c698-4c94-a5a9-53bbf8972b64",
                "counsel_adequate_bf": None,
                "counsel_breast": None,
                "counsel_exclusive_bf": 1,
                "counsel_increase_food_bf": 1,
                "counsel_methods": None,
                "counsel_only_milk": None,
                "skin_to_skin": None,
                "is_ebf": 1,
                "water_or_milk": None,
                "other_milk_to_child": 0,
                "tea_other": None,
                "eating": None,
                "not_breastfeeding": None,
                "unscheduled_visit": 0,
                "days_visit_late": 2,
                "next_visit": date(2017, 8, 23)
            }])
