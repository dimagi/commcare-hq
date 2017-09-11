from corehq.apps.data_interfaces.tests.util import create_case
from corehq.apps.locations.tests.util import make_loc, setup_location_types
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from custom.icds.case_relationships import (
    child_health_case_from_tasks_case,
    ccs_record_case_from_tasks_case,
    child_person_case_from_child_health_case,
    mother_person_case_from_child_person_case,
    mother_person_case_from_ccs_record_case,
    mother_person_case_from_child_health_case,
    child_person_case_from_tasks_case,
)
from custom.icds.const import AWC_LOCATION_TYPE_CODE, SUPERVISOR_LOCATION_TYPE_CODE
from custom.icds.exceptions import CaseRelationshipError
from custom.icds.tests.base import BaseICDSTest


class CaseRelationshipTest(BaseICDSTest):

    @classmethod
    def setUpClass(cls):
        super(CaseRelationshipTest, cls).setUpClass()
        cls.mother_person_case = cls.create_case('person')
        cls.child_person_case = cls.create_case(
            'person',
            parent_case_id=cls.mother_person_case.case_id,
            parent_identifier='mother',
            parent_relationship='child'
        )
        cls.child_health_case = cls.create_case(
            'child_health',
            parent_case_id=cls.child_person_case.case_id,
            parent_identifier='parent',
            parent_relationship='extension'
        )
        cls.child_tasks_case = cls.create_case(
            'tasks',
            parent_case_id=cls.child_health_case.case_id,
            parent_identifier='parent',
            parent_relationship='extension',
            update={'tasks_type': 'child'},
        )
        cls.ccs_record_case = cls.create_case(
            'ccs_record',
            parent_case_id=cls.mother_person_case.case_id,
            parent_case_type=cls.mother_person_case.type,
            parent_identifier='parent',
            parent_relationship='child'
        )
        cls.mother_tasks_case = cls.create_case(
            'tasks',
            parent_case_id=cls.ccs_record_case.case_id,
            parent_case_type=cls.ccs_record_case.type,
            parent_identifier='parent',
            parent_relationship='extension',
            update={'tasks_type': 'pregnancy'},
        )

    def test_relationships(self):
        self.assertEqual(
            child_health_case_from_tasks_case(self.child_tasks_case).case_id,
            self.child_health_case.case_id
        )

        self.assertEqual(
            ccs_record_case_from_tasks_case(self.mother_tasks_case).case_id,
            self.ccs_record_case.case_id
        )

        self.assertEqual(
            child_person_case_from_child_health_case(self.child_health_case).case_id,
            self.child_person_case.case_id
        )

        self.assertEqual(
            mother_person_case_from_child_person_case(self.child_person_case).case_id,
            self.mother_person_case.case_id
        )

        self.assertEqual(
            mother_person_case_from_ccs_record_case(self.ccs_record_case).case_id,
            self.mother_person_case.case_id
        )

        self.assertEqual(
            mother_person_case_from_child_health_case(self.child_health_case).case_id,
            self.mother_person_case.case_id
        )

        self.assertEqual(
            child_person_case_from_tasks_case(self.child_tasks_case).case_id,
            self.child_person_case.case_id
        )

    def test_case_type_mismatch(self):
        with self.assertRaises(ValueError):
            child_health_case_from_tasks_case(self.child_person_case)

    def test_parent_case_type_mismatch(self):
        with self.assertRaises(CaseRelationshipError):
            child_health_case_from_tasks_case(self.mother_tasks_case)


class CustomRecipientTest(BaseICDSTest):
    domain = 'icds-custom-recipient-test'

    @classmethod
    def setUpClass(cls):
        super(CustomRecipientTest, cls).setUpClass()
        cls.mother_person_case = cls.create_case('person')
        cls.child_person_case = cls.create_case(
            'person',
            cls.mother_person_case.case_id,
            cls.mother_person_case.type,
            'mother',
            'child'
        )
        cls.child_health_extension_case = cls.create_case(
            'child_health',
            cls.child_person_case.case_id,
            cls.child_person_case.type,
            'parent',
            'extension'
        )
        cls.lone_child_health_extension_case = cls.create_case('child_health')
        cls.ccs_record_case = cls.create_case(
            'ccs_record',
            cls.mother_person_case.case_id,
            cls.mother_person_case.type,
            'parent',
            'child'
        )

        cls.location_types = setup_location_types(cls.domain,
            [SUPERVISOR_LOCATION_TYPE_CODE, AWC_LOCATION_TYPE_CODE])

        cls.ls1 = make_loc('ls1', domain=cls.domain, type=SUPERVISOR_LOCATION_TYPE_CODE)
        cls.awc1 = make_loc('awc1', domain=cls.domain, type=AWC_LOCATION_TYPE_CODE, parent=cls.ls1)
        cls.awc2 = make_loc('awc2', domain=cls.domain, type=AWC_LOCATION_TYPE_CODE, parent=None)

    def test_mother_person_case_from_child_health_case(self):
        for cls in (CaseAlertScheduleInstance, CaseTimedScheduleInstance):
            self.assertEqual(
                cls(
                    domain=self.domain,
                    case_id=self.child_health_extension_case.case_id,
                    recipient_type='CustomRecipient',
                    recipient_id='ICDS_MOTHER_PERSON_CASE_FROM_CHILD_HEALTH_CASE'
                ).recipient.case_id,
                self.mother_person_case.case_id
            )

            self.assertIsNone(
                cls(
                    domain=self.domain,
                    case_id=self.lone_child_health_extension_case.case_id,
                    recipient_type='CustomRecipient',
                    recipient_id='ICDS_MOTHER_PERSON_CASE_FROM_CHILD_HEALTH_CASE'
                ).recipient
            )

    def test_supervisor_from_awc_owner(self):
        for cls in (CaseAlertScheduleInstance, CaseTimedScheduleInstance):
            with create_case(self.domain, 'person', owner_id=self.awc1.location_id) as case:
                self.assertEqual(
                    cls(
                        domain=self.domain,
                        case_id=case.case_id,
                        recipient_type='CustomRecipient',
                        recipient_id='ICDS_SUPERVISOR_FROM_AWC_OWNER'
                    ).recipient,
                    self.ls1
                )

            with create_case(self.domain, 'person', owner_id=self.awc2.location_id) as case:
                self.assertIsNone(
                    cls(
                        domain=self.domain,
                        case_id=case.case_id,
                        recipient_type='CustomRecipient',
                        recipient_id='ICDS_SUPERVISOR_FROM_AWC_OWNER'
                    ).recipient
                )

            with create_case(self.domain, 'person') as case:
                self.assertIsNone(
                    cls(
                        domain=self.domain,
                        case_id=case.case_id,
                        recipient_type='CustomRecipient',
                        recipient_id='ICDS_SUPERVISOR_FROM_AWC_OWNER'
                    ).recipient
                )
