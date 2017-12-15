from corehq.apps.data_interfaces.tests.util import create_case
from corehq.apps.hqcase.utils import update_case
from corehq.apps.reminders.models import CaseReminder
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from custom.enikshay.const import LOCATION_SITE_CODE_MEHSANA
from custom.enikshay.messaging.custom_recipients import (
    agency_user_case_from_voucher_fulfilled_by_id,
    beneficiary_registration_recipients,
    located_in_mehsana,
    person_case_from_voucher_case,
    prescription_voucher_alert_recipients,
)
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin, ENikshayLocationStructureMixin
from django.test import TestCase, override_settings


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class ENikshayCustomRecipientsTest(ENikshayCaseStructureMixin, ENikshayLocationStructureMixin, TestCase):

    def setUp(self):
        super(ENikshayCustomRecipientsTest, self).setUp()
        self.create_case_structure()

    def tearDown(self):
        super(ENikshayCustomRecipientsTest, self).tearDown()
        FormProcessorTestUtils.delete_all_cases(domain=self.domain)

    def create_user_case(self, user):
        create_case_kwargs = {
            'external_id': user.get_id,
            'update': {'hq_user_id': user.get_id},
        }
        return create_case(self.domain, 'commcare-user', **create_case_kwargs)

    def test_person_case_from_voucher_case(self):
        prescription = self.create_prescription_case()
        voucher = self.create_voucher_case(prescription.case_id)

        self.assertIsNone(
            person_case_from_voucher_case(None, CaseReminder(domain=self.domain))
        )

        self.assertIsNone(
            person_case_from_voucher_case(None, CaseReminder(domain=self.domain, case_id=prescription.case_id))
        )

        self.assertEqual(
            person_case_from_voucher_case(None, CaseReminder(domain=self.domain, case_id=voucher.case_id)).case_id,
            self.person_id
        )

    def test_agency_user_case_from_voucher_fulfilled_by_id(self):
        prescription = self.create_prescription_case()
        voucher = self.create_voucher_case(prescription.case_id)

        self.assertIsNone(
            agency_user_case_from_voucher_fulfilled_by_id(
                None,
                CaseReminder(domain=self.domain)
            )
        )

        self.assertIsNone(
            agency_user_case_from_voucher_fulfilled_by_id(
                None,
                CaseReminder(domain=self.domain, case_id=voucher.case_id)
            )
        )

        user = CommCareUser.create(self.domain, 'mobile', 'password')
        update_case(self.domain, voucher.case_id, case_properties={'voucher_fulfilled_by_id': user.get_id})

        with self.create_user_case(user) as user_case: 
            self.assertEqual(
                agency_user_case_from_voucher_fulfilled_by_id(
                    None,
                    CaseReminder(domain=self.domain, case_id=voucher.case_id)
                ).case_id,
                user_case.case_id
            )

    def test_beneficiary_registration_recipients(self):
        located_in_mehsana.clear(self.phi)
        self.dto.site_code = LOCATION_SITE_CODE_MEHSANA
        self.dto.save()
        self.assign_person_to_location(self.phi.location_id)

        update_case(self.domain, self.person_id, case_properties={'fo': self.pcc.location_id})
        user = CommCareUser.create(self.domain, 'mobile', 'password', location=self.pcc)

        # No user case created yet
        result = beneficiary_registration_recipients(
            None,
            CaseReminder(domain=self.domain, case_id=self.person_id)
        )
        self.assertTrue(isinstance(result, CommCareCaseSQL))
        self.assertEqual(result.case_id, self.person_id)

        # Create user case
        with self.create_user_case(user) as user_case: 
            result = beneficiary_registration_recipients(
                None,
                CaseReminder(domain=self.domain, case_id=self.person_id)
            )
            self.assertTrue(isinstance(result, list))
            self.assertEqual(
                [case.case_id for case in result],
                [self.person_id, user_case.case_id]
            )

            # Test location outside Mehsana
            located_in_mehsana.clear(self.phi)
            self.dto.site_code = 'dto-other'
            self.dto.save()

            result = beneficiary_registration_recipients(
                None,
                CaseReminder(domain=self.domain, case_id=self.person_id)
            )
            self.assertTrue(isinstance(result, CommCareCaseSQL))
            self.assertEqual(result.case_id, self.person_id)

    def test_prescription_voucher_alert_recipients(self):
        located_in_mehsana.clear(self.phi)
        self.dto.site_code = LOCATION_SITE_CODE_MEHSANA
        self.dto.save()
        self.assign_person_to_location(self.phi.location_id)

        prescription = self.create_prescription_case()
        voucher = self.create_voucher_case(prescription.case_id)

        user = CommCareUser.create(self.domain, 'mobile', 'password', location=self.phi)

        # No user case created yet
        result = prescription_voucher_alert_recipients(
            None,
            CaseReminder(domain=self.domain, case_id=voucher.case_id)
        )
        self.assertTrue(isinstance(result, CommCareCaseSQL))
        self.assertEqual(result.case_id, self.person_id)

        # Create user case
        with self.create_user_case(user) as user_case: 
            result = prescription_voucher_alert_recipients(
                None,
                CaseReminder(domain=self.domain, case_id=voucher.case_id)
            )
            self.assertTrue(isinstance(result, list))
            self.assertEqual(
                [case.case_id for case in result],
                [self.person_id, user_case.case_id]
            )

            # Test location outside Mehsana
            located_in_mehsana.clear(self.phi)
            self.dto.site_code = 'dto-other'
            self.dto.save()

            result = prescription_voucher_alert_recipients(
                None,
                CaseReminder(domain=self.domain, case_id=voucher.case_id)
            )
            self.assertTrue(isinstance(result, CommCareCaseSQL))
            self.assertEqual(result.case_id, self.person_id)
