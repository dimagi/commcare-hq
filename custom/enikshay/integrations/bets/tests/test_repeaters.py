from datetime import date

from django.test import override_settings

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.const import ENROLLED_IN_PRIVATE, PRESCRIPTION_TOTAL_DAYS_THRESHOLD
from custom.enikshay.integrations.bets.const import DRUG_REFILL_EVENT
from custom.enikshay.integrations.bets.repeater_generators import ChemistBETSVoucherPayloadGenerator, \
    BETS180TreatmentPayloadGenerator, BETSSuccessfulTreatmentPayloadGenerator, \
    BETSDiagnosisAndNotificationPayloadGenerator, BETSAYUSHReferralPayloadGenerator, BETSDrugRefillPayloadGenerator
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
        self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        prescription = self.create_prescription_case()
        voucher = self.create_voucher_case(
            prescription.case_id, {
                "voucher_type": "prescription",
                'state': 'not approved'
            }
        )
        self.assertEqual(0, len(self.repeat_records().all()))

        # voucher approved
        update_case(self.domain, voucher.case_id, {"state": "approved"})
        self.assertEqual(1, len(self.repeat_records().all()))

        # Changing state to some other state doesn't create another record
        update_case(self.domain, voucher.case_id, {"state": "foo"})
        self.assertEqual(1, len(self.repeat_records().all()))

        # Approving voucher again doesn't create new record
        payload_generator = ChemistBETSVoucherPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), voucher, None)
        update_case(self.domain, voucher.case_id, {"state": "approved"})
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
        cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        update_case(
            self.domain,
            self.episode_id,
            {
                'prescription_total_days': 20,
                ENROLLED_IN_PRIVATE: "true",
            },
        )
        case = cases[self.episode_id]
        self.assertEqual(0, len(self.repeat_records().all()))

        # meet trigger conditions
        update_case(self.domain, case.case_id, {
            "prescription_total_days": 181,
        })
        self.assertEqual(1, len(self.repeat_records().all()))

        # trigger only once
        payload_generator = BETS180TreatmentPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), case, None)
        update_case(self.domain, case.case_id, {"prescription_total_days": "182"})
        self.assertEqual(1, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class BETSDrugRefillRepeaterTest(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):
    def setUp(self):
        super(BETSDrugRefillRepeaterTest, self).setUp()
        self.repeater = BETSDrugRefillRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_trigger(self):

        # Create case that doesn't meet trigger
        cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        update_case(
            self.domain,
            self.episode_id,
            {
                ENROLLED_IN_PRIVATE: "true",
            },
        )
        case = cases[self.episode_id]
        self.assertEqual(0, len(self.repeat_records().all()))

        # Pass one threshold
        update_case(self.domain, case.case_id, {PRESCRIPTION_TOTAL_DAYS_THRESHOLD.format(30): date(2017, 1, 1)})
        self.assertEqual(1, len(self.repeat_records().all()))

        # Pass a second threshold
        update_case(self.domain, case.case_id, {
            "event_{}_{}".format(DRUG_REFILL_EVENT, 30): "sent",
            PRESCRIPTION_TOTAL_DAYS_THRESHOLD.format(60): date(2017, 1, 2)
        })
        self.assertEqual(2, len(self.repeat_records().all()))
        self.assertEqual(
            BETSDrugRefillPayloadGenerator._get_prescription_threshold_to_send(
                CaseAccessors(case.domain).get_case(case.case_id).dynamic_case_properties()
            ),
            60
        )

        # Attempt to pass two thresholds at once
        update_case(
            self.domain,
            case.case_id,
            {
                PRESCRIPTION_TOTAL_DAYS_THRESHOLD.format(90): date(2017, 1, 3),
                PRESCRIPTION_TOTAL_DAYS_THRESHOLD.format(120): date(2017, 1, 3)
            }
        )
        # record count does not increase
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
        cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        update_case(
            self.domain,
            self.episode_id,
            {
                'treatment_outcome': 'not_evaluated',
                'prescription_total_days': 200,
                ENROLLED_IN_PRIVATE: "true",
            },
        )
        case = cases[self.episode_id]
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
        cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        update_case(
            self.domain,
            self.episode_id,
            {
                'bets_first_prescription_voucher_redeemed': 'false',
                ENROLLED_IN_PRIVATE: "true",
            },
        )
        case = cases[self.episode_id]
        self.assertEqual(0, len(self.repeat_records().all()))

        # Meet trigger
        update_case(self.domain, case.case_id, {"bets_first_prescription_voucher_redeemed": "true"})
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
        cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        update_case(
            self.domain,
            self.episode_id,
            {
                'bets_first_prescription_voucher_redeemed': 'false',
                'created_by_user_type': 'pac',
                ENROLLED_IN_PRIVATE: "true",
            },
        )
        self.assertEqual(0, len(self.repeat_records().all()))

        # Meet trigger
        update_case(
            self.domain, self.episode_id, {"bets_first_prescription_voucher_redeemed": "true"}
        )
        self.assertEqual(1, len(self.repeat_records().all()))

        # Make sure same case doesn't trigger event again
        payload_generator = BETSAYUSHReferralPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), cases[self.episode_id], None)
        update_case(self.domain, self.episode_id, {"bets_first_prescription_voucher_redeemed": "false"})
        update_case(self.domain, self.episode_id, {"bets_first_prescription_voucher_redeemed": "true"})
        self.assertEqual(1, len(self.repeat_records().all()))
