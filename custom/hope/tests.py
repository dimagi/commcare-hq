
# Built-in imports
from datetime import datetime

# Django imports
from django.test import TestCase

# External libraries
from casexml.apps.case.models import CommCareCase

# CommCare HQ imports
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from custom.hope.models import HOPECase

class TestHOPECaseResource(TestCase):
    """
    Smoke test for the HOPECase wrapper on CommCareCase to make sure that the
    derived properties do not just immediately crash.
    """

    def setUp(self):
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)
        self.username = 'rudolph@qwerty.commcarehq.org'
        self.password = '***'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

    def hit_every_HOPE_property(self, hope_case):
        """
        Helper method that can be applied to a variety of HOPECase objects
        to make sure none of the _HOPE properties crash
        """

        # test mother other properties
        hope_case._HOPE_mother_mother_name
        hope_case._HOPE_mother_husband_name
        hope_case._HOPE_mother_program_cd
        hope_case._HOPE_mother_bank_account_number
        hope_case._HOPE_mother_bank_id
        hope_case._HOPE_mother_bank_branch_id
        hope_case._HOPE_mother_ifsc_code
        hope_case._HOPE_mother_full_mcts_id
        hope_case._HOPE_asha_id
        hope_case._HOPE_asha_bank_account_number
        hope_case._HOPE_asha_bank_id
        hope_case._HOPE_asha_bank_branch_id
        hope_case._HOPE_asha_ifsc_code

        # test child other properties
        hope_case._HOPE_child_parent_mother_name
        hope_case._HOPE_child_parent_husband_name
        hope_case._HOPE_child_parent_bank_account_number
        hope_case._HOPE_child_parent_bank_id
        hope_case._HOPE_child_parent_bank_branch_id
        hope_case._HOPE_child_parent_ifsc_code
        hope_case._HOPE_child_parent_full_mcts_id
        hope_case._HOPE_child_full_child_mcts_id
        hope_case._HOPE_asha_id
        hope_case._HOPE_asha_bank_account_number
        hope_case._HOPE_asha_bank_id
        hope_case._HOPE_asha_bank_branch_id
        hope_case._HOPE_asha_ifsc_code

        # test mother events attributes
        hope_case._HOPE_mother_anc_1_date
        hope_case._HOPE_mother_anc_2_date
        hope_case._HOPE_mother_anc_3_date
        hope_case._HOPE_mother_anc_4_date
        hope_case._HOPE_mother_all_anc_doses_given
        hope_case._HOPE_mother_patient_reg_num
        hope_case._HOPE_mother_registration_date
        hope_case._HOPE_mother_existing_child_count
        hope_case._HOPE_mother_age
        hope_case._HOPE_mother_bpl_indicator
        hope_case._HOPE_mother_delivery_date
        hope_case._HOPE_mother_time_of_birth
        hope_case._HOPE_mother_tubal_ligation
        hope_case._HOPE_mother_area_indicator
        hope_case._HOPE_mother_ifa1_date
        hope_case._HOPE_mother_ifa2_date
        hope_case._HOPE_mother_ifa3_date
        hope_case._HOPE_mother_all_ifa_doses_given
        hope_case._HOPE_mother_tt_1_date
        hope_case._HOPE_mother_tt_2_date
        hope_case._HOPE_mother_all_tt_doses_given

        # test child events attributes
        hope_case._HOPE_child_child_name
        hope_case._HOPE_child_mother_name
        hope_case._HOPE_child_number_of_visits
        hope_case._HOPE_child_bcg_indicator
        hope_case._HOPE_child_opv_1_indicator
        hope_case._HOPE_child_dpt_1_indicator
        hope_case._HOPE_child_delivery_type
        hope_case._HOPE_child_child_name
        hope_case._HOPE_child_mother_name
        hope_case._HOPE_child_mother_husband_name
        hope_case._HOPE_child_dpt_1_date
        hope_case._HOPE_child_opv_1_date
        hope_case._HOPE_child_hep_b_1_date
        hope_case._HOPE_child_dpt_2_date
        hope_case._HOPE_child_opv_2_date
        hope_case._HOPE_child_hep_b_2_date
        hope_case._HOPE_child_dpt_3_date
        hope_case._HOPE_child_opv_3_date
        hope_case._HOPE_child_hep_b_3_date
        hope_case._HOPE_child_measles_date
        hope_case._HOPE_child_dob
        hope_case._HOPE_child_all_dpt1_opv1_hb1_doses_given
        hope_case._HOPE_child_all_dpt2_opv2_hb2_doses_given
        hope_case._HOPE_child_all_dpt3_opv3_hb3_doses_given
        hope_case._HOPE_child_measles_dose_given


    def test_derived_properties(self):
        """
        Smoke test that the HOPE properties do not crash on a pretty empty CommCareCase
        """

        modify_date = datetime.utcnow()

        backend_case = CommCareCase(server_modified_on=modify_date, domain=self.domain.name)
        backend_case.save()

        # Rather than a re-fetch, this simulates the common case where it is pulled from ES
        hope_case = HOPECase.wrap(backend_case.to_json())

        self.hit_every_HOPE_property(hope_case)

        backend_case.delete()

