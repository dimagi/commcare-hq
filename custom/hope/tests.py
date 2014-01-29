
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

        hope_case._HOPE_all_anc_doses_given
        hope_case._HOPE_all_dpt1_opv1_hb1_doses_given
        hope_case._HOPE_all_dpt2_opv2_hb2_doses_given
        hope_case._HOPE_all_dpt3_opv3_hb3_doses_given
        hope_case._HOPE_all_ifa_doses_given
        hope_case._HOPE_all_tt_doses_given
        hope_case._HOPE_bcg_indicator
        hope_case._HOPE_delivery_nature
        hope_case._HOPE_delivery_type
        hope_case._HOPE_existing_child_count
        hope_case._HOPE_ifa1_date
        hope_case._HOPE_ifa2_date
        hope_case._HOPE_ifa3_date
        hope_case._HOPE_measles_dose_given
        hope_case._HOPE_number_of_visits
        hope_case._HOPE_opv_1_indicator
        hope_case._HOPE_registration_date
        hope_case._HOPE_time_of_birth
        hope_case._HOPE_tubal_ligation

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

