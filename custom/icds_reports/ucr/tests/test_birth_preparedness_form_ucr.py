from __future__ import absolute_import, unicode_literals

from datetime import date
from decimal import Decimal

from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestBirthPreparednessForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-dashboard_birth_preparedness_forms"

    def test_birth_preparedness_form(self):
        self._test_data_source_results(
            'birth_preparedness_form_v10326',
            [{
                "doc_id": None,
                "timeend": None,
                "ccs_record_case_id": "52587bea-68c7-4bf7-a4b6-ed3ff90b5069",
                "immediate_breastfeeding": None,
                "using_ifa": None,
                "play_birth_preparedness_vid": None,
                "counsel_preparation": None,
                "play_family_planning_vid": None,
                "conceive": None,
                "counsel_accessible_ppfp": None,
                "anemia": 0,
                "ifa_last_seven_days": None,
                "eating_extra": 1,
                "resting": 1,
                "anc_weight": None,
                "anc_blood_pressure": 0,
                "bp_sys": None,
                "bp_dia": None,
                "anc_abnormalities": None,
                "anc_hemoglobin": None,
                "bleeding": None,
                "swelling": None,
                "blurred_vision": None,
                "convulsions": None,
                "rupture": None,
                "unscheduled_visit": 1,
                "days_visit_late": None,
                "next_visit": date(2017, 7, 18)
            }]
        )

    def test_birth_preparedness_form_anemia(self):
        self._test_data_source_results(
            'birth_preparedness_form_anemia_v10326',
            [{
                "doc_id": None,
                "timeend": None,
                "ccs_record_case_id": "b2aed19b-0aac-4a47-a578-fddff3b84039",
                "immediate_breastfeeding": None,
                "using_ifa": 1,
                "play_birth_preparedness_vid": None,
                "counsel_preparation": None,
                "play_family_planning_vid": None,
                "conceive": None,
                "counsel_accessible_ppfp": None,
                "anemia": 1,
                "ifa_last_seven_days": None,
                "eating_extra": 1,
                "resting": 1,
                "anc_weight": 50,
                "anc_blood_pressure": 1,
                "bp_sys": 100,
                "bp_dia": 50,
                "anc_abnormalities": 0,
                "anc_hemoglobin": Decimal('2.0'),
                "bleeding": None,
                "swelling": None,
                "blurred_vision": None,
                "convulsions": None,
                "rupture": None,
                "unscheduled_visit": 1,
                "days_visit_late": None,
                "next_visit": date(2018, 2, 21)
            }]
        )
