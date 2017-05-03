import uuid
from django.test import override_settings

from corehq.util.test_utils import create_and_save_a_case
from custom.enikshay.integrations.bets.repeater_generators import ChemistBETSVoucherPayloadGenerator, \
    BETS180TreatmentPayloadGenerator, BETSSuccessfulTreatmentPayloadGenerator, \
    BETSDiagnosisAndNotificationPayloadGenerator, BETSAYUSHReferralPayloadGenerator
from custom.enikshay.integrations.bets.repeaters import ChemistBETSVoucherRepeater, BETS180TreatmentRepeater, \
    BETSDrugRefillRepeater, BETSSuccessfulTreatmentRepeater, BETSDiagnosisAndNotificationRepeater, \
    BETSAYUSHReferralRepeater
from custom.enikshay.integrations.ninetyninedots.tests.test_repeaters import ENikshayRepeaterTestBase, MockResponse

from custom.enikshay.tests.utils import ENikshayLocationStructureMixin
from custom.enikshay.case_utils import update_case


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestVoucherRepeater(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):

    def setUp(self):
        super(TestVoucherRepeater, self).setUp()

        self.repeater = ChemistBETSVoucherRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.white_listed_case_types = ['voucher']
        self.repeater.save()

    def test_trigger(self):
        # voucher not approved
        case = create_and_save_a_case(
            self.domain,
            uuid.uuid4().hex,
            case_type="voucher",
            case_name="my voucher",
            case_properties={
                "voucher_type": "prescription",
                'state': 'not approved'
            },
        )
        self.assertEqual(0, len(self.repeat_records().all()))

        # voucher approved
        update_case(self.domain, case.case_id, {"state": "approved"})
        self.assertEqual(1, len(self.repeat_records().all()))

        # Changing state to some other state doesn't create another record
        update_case(self.domain, case.case_id, {"state": "foo"})
        self.assertEqual(1, len(self.repeat_records().all()))

        # Approving voucher again doesn't create new record
        payload_generator = ChemistBETSVoucherPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), case, None)
        update_case(self.domain, case.case_id, {"state": "approved"})
        self.assertEqual(1, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestBETS180TreatmentRepeater(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):
    def setUp(self):
        super(TestBETS180TreatmentRepeater, self).setUp()
        self.repeater = BETS180TreatmentRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_trigger(self):
        # episode that does not meet trigger
        case = create_and_save_a_case(
            self.domain,
            uuid.uuid4().hex,
            case_type="episode",
            case_name="my episode",
            case_properties={
                'adherence_total_doses_taken': 150,
                'treatment_outcome': 'not_evaluated'
            },
        )
        self.assertEqual(0, len(self.repeat_records().all()))

        # meet trigger conditions
        update_case(self.domain, case.case_id, {
            "treatment_outcome": "cured",
            "adherence_total_doses_taken": 180,
        })
        self.assertEqual(1, len(self.repeat_records().all()))

        # trigger only once
        payload_generator = BETS180TreatmentPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), case, None)
        update_case(self.domain, case.case_id, {"adherence_total_doses_taken": "181"})
        self.assertEqual(1, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class BETSDrugRefillRepeaterTest(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):
    def setUp(self):
        super(BETSDrugRefillRepeaterTest, self).setUp()
        self.repeater = BETSDrugRefillRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.white_listed_case_types = ['voucher']
        self.repeater.save()

    def test_trigger(self):

        # make prescription and episode too
        self.create_case_structure()
        voucher = self.create_prescription_voucher({"state": "foo"})
        self.assertEqual(0, len(self.repeat_records().all()))

        # update voucher to meet the trigger, but is only first voucher (need 2 to trigger)
        update_case(self.domain, voucher.case_id, {"state": "fulfilled"})
        self.assertEqual(0, len(self.repeat_records().all()))

        # Meet the trigger condition
        voucher_2 = self.create_prescription_voucher({"state": "foo"})
        update_case(self.domain, voucher_2.case_id, {"state": "fulfilled"})
        self.assertEqual(1, len(self.repeat_records().all()))

        # Create another case that meets the trigger again
        voucher_3 = self.create_prescription_voucher({"state": "foo"})
        update_case(self.domain, voucher_3.case_id, {"state": "fulfilled"})
        self.assertEqual(2, len(self.repeat_records().all()))

        # Don't trigger on other update to voucher
        update_case(self.domain, voucher.case_id, {"foo": "bar"})
        self.assertEqual(2, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class BETSSuccessfulTreatmentRepeaterTest(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):
    def setUp(self):
        super(BETSSuccessfulTreatmentRepeaterTest, self).setUp()
        self.repeater = BETSSuccessfulTreatmentRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_trigger(self):
        # Create case that doesn't meet trigger
        case = create_and_save_a_case(
            self.domain,
            uuid.uuid4().hex,
            case_type="episode",
            case_name="my episode",
            case_properties={
                'treatment_outcome': 'not_evaluated'
            },
        )
        self.assertEqual(0, len(self.repeat_records().all()))

        # Meet trigger
        update_case(self.domain, case.case_id, {"treatment_outcome": "cured"})
        self.assertEqual(1, len(self.repeat_records().all()))

        # Make sure same case doesn't trigger event again
        payload_generator = BETSSuccessfulTreatmentPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), case, None)
        update_case(self.domain, case.case_id, {"foo": "bar"})
        self.assertEqual(1, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class BETSDiagnosisAndNotificationRepeaterTest(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):
    def setUp(self):
        super(BETSDiagnosisAndNotificationRepeaterTest, self).setUp()
        self.repeater = BETSDiagnosisAndNotificationRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_trigger(self):
        # Create case that doesn't meet trigger
        case = create_and_save_a_case(
            self.domain,
            uuid.uuid4().hex,
            case_type="episode",
            case_name="my episode",
            case_properties={
                'pending_registration': 'yes',
                'nikshay_registered': 'false',
            },
        )
        self.assertEqual(0, len(self.repeat_records().all()))

        # Meet trigger
        update_case(self.domain, case.case_id, {"nikshay_registered": "true", 'pending_registration': "no"})
        self.assertEqual(1, len(self.repeat_records().all()))

        # Make sure same case doesn't trigger event again
        payload_generator = BETSDiagnosisAndNotificationPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), case, None)
        update_case(self.domain, case.case_id, {"foo": "bar"})
        self.assertEqual(1, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class BETSAYUSHReferralRepeaterTest(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):
    def setUp(self):
        super(BETSAYUSHReferralRepeaterTest, self).setUp()
        self.repeater = BETSAYUSHReferralRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_trigger(self):
        # Create case that doesn't meet trigger
        case = create_and_save_a_case(
            self.domain,
            uuid.uuid4().hex,
            case_type="episode",
            case_name="my episode",
            case_properties={
                'presumptive_referral_by_ayush': 'false',
                'nikshay_registered': 'false',
            },
        )
        self.assertEqual(0, len(self.repeat_records().all()))

        # Meet trigger
        update_case(
            self.domain, case.case_id, {"nikshay_registered": "true", 'presumptive_referral_by_ayush': "123"}
        )
        self.assertEqual(1, len(self.repeat_records().all()))

        # Make sure same case doesn't trigger event again
        payload_generator = BETSAYUSHReferralPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), case, None)
        update_case(self.domain, case.case_id, {"nikshay_registered": "false"})
        update_case(self.domain, case.case_id, {"nikshay_registered": "true"})
        self.assertEqual(1, len(self.repeat_records().all()))
