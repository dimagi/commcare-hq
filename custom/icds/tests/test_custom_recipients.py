from corehq.apps.data_interfaces.tests.util import create_case
from corehq.apps.locations.tests.util import make_loc, setup_location_types
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from custom.icds.const import (
    AWC_LOCATION_TYPE_CODE,
    SUPERVISOR_LOCATION_TYPE_CODE,
)
from custom.icds.messaging.custom_recipients import (
    recipient_mother_person_case_from_ccs_record_case,
    recipient_mother_person_case_from_ccs_record_case_excl_migrated_or_opted_out,
    recipient_mother_person_case_from_child_health_case,
    recipient_mother_person_case_from_child_person_case,
    supervisor_from_awc_owner,
)
from custom.icds.tests.base import BaseICDSTest


class CustomRecipientTest(BaseICDSTest):
    domain = 'icds-custom-recipient-test'

    @classmethod
    def setUpClass(cls):
        super(CustomRecipientTest, cls).setUpClass()
        cls.create_basic_related_cases()

        cls.location_types = setup_location_types(cls.domain,
            [SUPERVISOR_LOCATION_TYPE_CODE, AWC_LOCATION_TYPE_CODE])

        cls.ls1 = make_loc('ls1', domain=cls.domain, type=SUPERVISOR_LOCATION_TYPE_CODE)
        cls.awc1 = make_loc('awc1', domain=cls.domain, type=AWC_LOCATION_TYPE_CODE, parent=cls.ls1)
        cls.awc2 = make_loc('awc2', domain=cls.domain, type=AWC_LOCATION_TYPE_CODE, parent=None)

    def _test_recipient(self, custom_function, test_cases, test_attr="case_id"):
        for case_id, expected_case_id in test_cases:
            for cls in (CaseAlertScheduleInstance, CaseTimedScheduleInstance):
                schedule_instance = cls(domain=self.domain, case_id=case_id)
                actual = custom_function(schedule_instance)
                if expected_case_id is None:
                    self.assertIsNone(actual)
                else:
                    if test_attr:
                        actual = getattr(actual, test_attr)
                    self.assertEqual(actual, expected_case_id)

    def test_mother_person_case_from_ccs_record_case(self):
        self._test_recipient(
            recipient_mother_person_case_from_ccs_record_case,
            [
                (self.ccs_record_case.case_id, self.mother_person_case.case_id),
                (self.lone_ccs_record_case.case_id, None),
            ]
        )

    def test_mother_person_case_from_ccs_record_case_excl_migrated_or_opted_out(self):
        self._test_recipient(
            recipient_mother_person_case_from_ccs_record_case_excl_migrated_or_opted_out,
            [
                (self.ccs_record_case.case_id, self.mother_person_case.case_id),
                (self.migrated_mother_ccs_record_case.case_id, None),
                (self.opted_out_mother_ccs_record_case.case_id, None),
                (self.lone_ccs_record_case.case_id, None),
            ]
        )

    def test_mother_person_case_from_child_health_case(self):
        self._test_recipient(
            recipient_mother_person_case_from_child_health_case,
            [
                (self.child_health_case.case_id, self.mother_person_case.case_id),
                (self.lone_child_health_case.case_id, None),
            ]
        )

    def test_mother_person_case_from_child_person_case(self):
        self._test_recipient(
            recipient_mother_person_case_from_child_person_case,
            [
                (self.child_person_case.case_id, self.mother_person_case.case_id),
                (self.lone_child_person_case.case_id, None),
            ]
        )

    def test_supervisor_from_awc_owner(self):
        with create_case(self.domain, 'person', owner_id=self.awc1.location_id) as case:
            self._test_recipient(supervisor_from_awc_owner, [(case.case_id, self.ls1)], test_attr=None)

        with create_case(self.domain, 'person', owner_id=self.awc2.location_id) as case:
            self._test_recipient(supervisor_from_awc_owner, [(case.case_id, None)], test_attr=None)

        with create_case(self.domain, 'person') as case:
            self._test_recipient(supervisor_from_awc_owner, [(case.case_id, None)], test_attr=None)
