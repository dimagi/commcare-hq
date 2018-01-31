from __future__ import absolute_import
from datetime import date, datetime
import json
import mock

from django.test import override_settings, TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.motech.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from corehq.motech.repeaters.models import RepeatRecord
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from custom.enikshay.const import (
    ENROLLED_IN_PRIVATE,
    PRESCRIPTION_TOTAL_DAYS_THRESHOLD,
    TREATMENT_OUTCOME,
    TREATMENT_OUTCOME_DATE,
    LAST_VOUCHER_CREATED_BY_ID,
    NOTIFYING_PROVIDER_USER_ID,
    FIRST_PRESCRIPTION_VOUCHER_REDEEMED_DATE,
    FIRST_PRESCRIPTION_VOUCHER_REDEEMED,
)
from custom.enikshay.integrations.bets.const import (
    TREATMENT_180_EVENT,
    DRUG_REFILL_EVENT,
    SUCCESSFUL_TREATMENT_EVENT,
    DIAGNOSIS_AND_NOTIFICATION_EVENT,
    AYUSH_REFERRAL_EVENT,
)
from custom.enikshay.integrations.bets.repeater_generators import (
    ChemistBETSVoucherPayloadGenerator,
    BETS180TreatmentPayloadGenerator,
    BETSSuccessfulTreatmentPayloadGenerator,
    BETSDiagnosisAndNotificationPayloadGenerator,
    BETSAYUSHReferralPayloadGenerator,
    BETSDrugRefillPayloadGenerator,
)
from custom.enikshay.integrations.bets.repeaters import (
    ChemistBETSVoucherRepeater,
    BETS180TreatmentRepeater,
    BETSDrugRefillRepeater,
    BETSSuccessfulTreatmentRepeater,
    BETSDiagnosisAndNotificationRepeater,
    BETSAYUSHReferralRepeater,
    BETSLocationRepeater,
    BETSBeneficiaryRepeater,
    BETSUserRepeater,
)
from custom.enikshay.integrations.ninetyninedots.tests.test_repeaters import ENikshayRepeaterTestBase, MockResponse

from custom.enikshay.tests.utils import (
    ENikshayLocationStructureMixin, get_person_case_structure, setup_enikshay_locations)
from custom.enikshay.case_utils import update_case
import six


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class TestBetsResponseHandling(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):
    def setUp(self):
        super(TestBetsResponseHandling, self).setUp()
        user = CommCareUser.create(
            self.domain,
            "davos.shipwright@stannis.gov",
            "123",
        )
        self.repeater = BETSUserRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.save()
        self.repeat_record = RepeatRecord(
            repeater_id=self.repeater.get_id,
            payload_id=user.user_id,
            next_check=datetime.utcnow(),
        )

    def test_success(self):
        mock_response_json = {
            "meta": {
                "failCount": "0",
                "successCount": "1",
                "totalCount": "1",
            },
            "response": [
                {
                    "status": "Success",
                    "failureDescription": ""
                }
            ]
        }
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json = mock.MagicMock(return_value=mock_response_json)

        attempt = self.repeater.handle_response(mock_response, self.repeat_record)
        self.assertTrue(attempt.succeeded)

    def test_failure(self):
        mock_response_json = {
            "meta": {
                "failCount": "1",
                "successCount": "1",
                "totalCount": "2",
            },
            "response": [
                {
                    "status": "Success",
                    "failureDescription": ""
                },
                {
                    "status": "Partial",
                    "failureDescription": "yo"
                }
            ]
        }
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json = mock.MagicMock(return_value=mock_response_json)

        attempt = self.repeater.handle_response(mock_response, self.repeat_record)
        self.assertTrue(attempt.failure_reason)

    def test_failure_2(self):
        mock_response_json = {"status": "Failed", "code": "400"}
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json = mock.MagicMock(return_value=mock_response_json)

        attempt = self.repeater.handle_response(mock_response, self.repeat_record)
        self.assertTrue(attempt.failure_reason)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class TestVoucherPayload(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):

    def test_prescription_get_payload(self):
        self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        prescription = self.create_prescription_case()
        voucher = self.create_voucher_case(
            prescription.case_id, {
                "voucher_type": "prescription",
                "voucher_fulfilled_by_id": self.user.user_id,
                "voucher_approved_by_id": self.user.user_id,
                "voucher_fulfilled_by_location_id": self.pcc.location_id,
                "date_fulfilled": "2017-08-15",
                "voucher_id": "ABC-DEF-1123",
                "amount_approved": '9.2',  # this should be rounded to 9
            }
        )

        expected_payload = {"voucher_details": [{
            u"EventID": u"101",
            u"EventOccurDate": u"2017-08-15",
            u"BeneficiaryUUID": self.user.user_id,
            u"BeneficiaryType": u"chemist",
            u"Location": self.pcc.location_id,
            u"DTOLocation": self.dto.location_id,
            u"VoucherID": voucher.case_id,
            u"ReadableVoucherID": voucher.get_case_property('voucher_id'),
            u"Amount": u'9',
            u"InvestigationType": None,
            u"PersonId": self.person.attrs['update']['person_id'],
            u"AgencyId": self.username.split('@')[0],
            u"EnikshayApprover": u"Jon Snow",
            u"EnikshayRole": None,
            u"EnikshayApprovalDate": None,
        }]}

        self.assertDictEqual(
            expected_payload,
            json.loads(ChemistBETSVoucherPayloadGenerator(None).get_payload(None, voucher))
        )

    def test_investigation_get_payload(self):
        self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        prescription = self.create_prescription_case()
        voucher = self.create_voucher_case(
            prescription.case_id, {
                "voucher_type": "test",
                "voucher_approved_by_id": self.user.user_id,
                "voucher_fulfilled_by_id": self.user.user_id,
                "voucher_fulfilled_by_location_id": self.plc.location_id,
                "date_fulfilled": "2017-08-15",
                "voucher_id": "ABC-DEF-1123",
                "amount_approved": 10.0,
                "investigation_type": "xray",
            }
        )

        expected_payload = {"voucher_details": [{
            u"EventID": u"102",
            u"EventOccurDate": u"2017-08-15",
            u"BeneficiaryUUID": self.user.user_id,
            u"BeneficiaryType": u"lab",
            u"Location": self.plc.location_id,
            u"DTOLocation": self.dto.location_id,
            u"VoucherID": voucher.case_id,
            u"ReadableVoucherID": voucher.get_case_property('voucher_id'),
            u"Amount": u'10',
            u"InvestigationType": u"xray",
            u"PersonId": self.person.attrs['update']['person_id'],
            u"AgencyId": self.username.split('@')[0],
            u"EnikshayApprover": self.user.name,
            u"EnikshayRole": None,
            u"EnikshayApprovalDate": None,
        }]}

        self.assertDictEqual(
            expected_payload,
            json.loads(ChemistBETSVoucherPayloadGenerator(None).get_payload(None, voucher))
        )


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class TestIncentivePayload(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):
    def setUp(self):
        super(TestIncentivePayload, self).setUp()
        self.episode.attrs['update']['bets_notifying_provider_user_id'] = self.user._id

    def test_bets_180_treatment_payload(self):
        self.episode.attrs['update'][TREATMENT_OUTCOME] = "cured"
        self.episode.attrs['update'][TREATMENT_OUTCOME_DATE] = "2017-08-15"
        self.episode.attrs['update'][LAST_VOUCHER_CREATED_BY_ID] = self.user.user_id
        cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        episode = cases[self.episode_id]

        expected_payload = {"incentive_details": [{
            u"EventID": six.text_type(TREATMENT_180_EVENT),
            u"EventOccurDate": u"2017-08-15",
            u"BeneficiaryUUID": self.user.user_id,
            u"BeneficiaryType": u"mbbs",
            u"Location": self.pcp.location_id,
            u"DTOLocation": self.dto.location_id,
            u"EpisodeID": self.episode_id,
            u"PersonId": self.person.attrs['update']['person_id'],
            u"AgencyId": self.username.split('@')[0],
            u"EnikshayApprover": None,
            u"EnikshayRole": None,
            u"EnikshayApprovalDate": None,
        }]}
        self.assertDictEqual(
            expected_payload,
            json.loads(BETS180TreatmentPayloadGenerator(None).get_payload(None, episode))
        )

    def test_drug_refill_payload(self):
        self.episode.attrs['update'][PRESCRIPTION_TOTAL_DAYS_THRESHOLD.format(30)] = "2012-08-15"
        self.episode.attrs['update']["event_{}_{}".format(DRUG_REFILL_EVENT, 30)] = "sent"
        self.episode.attrs['update'][PRESCRIPTION_TOTAL_DAYS_THRESHOLD.format(60)] = "2017-08-15"
        cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        episode = cases[self.episode_id]

        expected_payload = {"incentive_details": [{
            u"EventID": six.text_type(DRUG_REFILL_EVENT),
            u"EventOccurDate": u"2017-08-15",
            u"BeneficiaryUUID": self.person_id,
            u"BeneficiaryType": u"patient",
            u"Location": self.pcp.location_id,
            u"DTOLocation": self.dto.location_id,
            u"EpisodeID": self.episode_id,
            u"PersonId": self.person.attrs['update']['person_id'],
            u"AgencyId": self.username.split('@')[0],
            u"EnikshayApprover": None,
            u"EnikshayRole": None,
            u"EnikshayApprovalDate": None,
        }]}
        self.assertDictEqual(
            expected_payload,
            json.loads(BETSDrugRefillPayloadGenerator(None).get_payload(None, episode))
        )

    def test_successful_treatment_payload(self):
        self.person.attrs['update']['last_owner'] = self.pcp.location_id
        self.person.attrs['owner_id'] = "_archive_"
        self.episode.attrs['update'][TREATMENT_OUTCOME_DATE] = "2017-08-15"
        self.episode.attrs['update'][TREATMENT_OUTCOME] = "cured"
        cases = self.create_case_structure()
        episode = cases[self.episode_id]

        expected_payload = {"incentive_details": [{
            u"EventID": six.text_type(SUCCESSFUL_TREATMENT_EVENT),
            u"EventOccurDate": u"2017-08-15",
            u"BeneficiaryUUID": self.person_id,
            u"BeneficiaryType": u"patient",
            u"Location": self.pcp.location_id,
            u"DTOLocation": self.dto.location_id,
            u"EpisodeID": self.episode_id,
            u"PersonId": self.person.attrs['update']['person_id'],
            u"AgencyId": self.username.split('@')[0],
            u"EnikshayApprover": None,
            u"EnikshayRole": None,
            u"EnikshayApprovalDate": None,
        }]}
        self.assertDictEqual(
            expected_payload,
            json.loads(BETSSuccessfulTreatmentPayloadGenerator(None).get_payload(None, episode))
        )

    def test_successful_treatment_payload_non_closed_case(self):
        self.episode.attrs['update']["prescription_total_days"] = 180
        self.episode.attrs['update'][TREATMENT_OUTCOME_DATE] = "2017-08-15"
        self.episode.attrs['update'][TREATMENT_OUTCOME] = "cured"
        self.person.attrs['owner_id'] = self.pcp.location_id
        cases = self.create_case_structure()
        episode = cases[self.episode_id]

        expected_payload = {"incentive_details": [{
            u"EventID": six.text_type(SUCCESSFUL_TREATMENT_EVENT),
            u"EventOccurDate": u"2017-08-15",
            u"BeneficiaryUUID": self.person_id,
            u"BeneficiaryType": u"patient",
            u"Location": self.pcp.location_id,
            u"DTOLocation": self.dto.location_id,
            u"EpisodeID": self.episode_id,
            u"PersonId": self.person.attrs['update']['person_id'],
            u"AgencyId": self.username.split('@')[0],
            u"EnikshayApprover": None,
            u"EnikshayRole": None,
            u"EnikshayApprovalDate": None,
        }]}
        self.assertDictEqual(
            expected_payload,
            json.loads(BETSSuccessfulTreatmentPayloadGenerator(None).get_payload(None, episode))
        )

    def test_diagnosis_and_notification_payload(self):
        date_today = u"2017-08-15"
        self.episode.attrs['update'][NOTIFYING_PROVIDER_USER_ID] = self.user.user_id
        self.episode.attrs['update'][FIRST_PRESCRIPTION_VOUCHER_REDEEMED_DATE] = date_today
        cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        episode = cases[self.episode_id]

        expected_payload = {"incentive_details": [{
            u"EventID": six.text_type(DIAGNOSIS_AND_NOTIFICATION_EVENT),
            u"EventOccurDate": date_today,
            u"BeneficiaryUUID": self.user.user_id,
            u"BeneficiaryType": u"mbbs",
            u"Location": self.pcp.location_id,
            u"DTOLocation": self.dto.location_id,
            u"EpisodeID": self.episode_id,
            u"PersonId": self.person.attrs['update']['person_id'],
            u"AgencyId": self.username.split('@')[0],
            u"EnikshayApprover": None,
            u"EnikshayRole": None,
            u"EnikshayApprovalDate": None,
        }]}
        self.assertDictEqual(
            expected_payload,
            json.loads(BETSDiagnosisAndNotificationPayloadGenerator(None).get_payload(None, episode))
        )

    def test_ayush_referral_payload(self):
        date_today = u"2017-08-15"
        self.pac.user_id = self.user.user_id
        self.pac.save()
        self.episode.attrs['update']['registered_by'] = self.pac.location_id
        self.episode.attrs['update'][FIRST_PRESCRIPTION_VOUCHER_REDEEMED_DATE] = date_today
        cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        episode = cases[self.episode_id]

        expected_payload = {"incentive_details": [{
            u"EventID": six.text_type(AYUSH_REFERRAL_EVENT),
            u"EventOccurDate": date_today,
            u"BeneficiaryUUID": self.user.user_id,
            u"BeneficiaryType": u"ayush_other",
            u"Location": self.pac.location_id,
            u"DTOLocation": self.dto.location_id,
            u"EpisodeID": self.episode_id,
            u"PersonId": self.person.attrs['update']['person_id'],
            u"AgencyId": self.username.split('@')[0],
            u"EnikshayApprover": None,
            u"EnikshayRole": None,
            u"EnikshayApprovalDate": None,
        }]}
        self.assertDictEqual(
            expected_payload,
            json.loads(BETSAYUSHReferralPayloadGenerator(None).get_payload(None, episode))
        )


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
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
                CaseAccessors(case.domain).get_case(case.case_id)
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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class BETSSuccessfulTreatmentRepeaterTest(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):
    def setUp(self):
        super(BETSSuccessfulTreatmentRepeaterTest, self).setUp()
        self.repeater = BETSSuccessfulTreatmentRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_treatment_outcome_trigger(self):
        # Create case that doesn't meet trigger
        cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        update_case(
            self.domain,
            self.episode_id,
            {
                'treatment_outcome': 'not_evaluated',
                'prescription_total_days': 100,
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

    def test_prescription_total_days_trigger(self):
        # Create case that doesn't meet trigger
        cases = self.create_case_structure()
        self.assign_person_to_location(self.pcp.location_id)
        update_case(
            self.domain,
            self.episode_id,
            {
                'treatment_outcome': 'not_evaluated',
                'prescription_total_days': 100,
                'treatment_options': 'fdc',
                ENROLLED_IN_PRIVATE: "true",
            },
        )
        case = cases[self.episode_id]
        self.assertEqual(0, len(self.repeat_records().all()))

        # Meet trigger
        # This property is normally set by the episode task
        update_case(self.domain, case.case_id, {'bets_date_prescription_threshold_met': '2017-08-08'})
        self.assertEqual(1, len(self.repeat_records().all()))

        # Make sure same case doesn't trigger event again
        payload_generator = BETSSuccessfulTreatmentPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), case, None)
        update_case(self.domain, case.case_id, {"foo": "bar"})
        self.assertEqual(1, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
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
                FIRST_PRESCRIPTION_VOUCHER_REDEEMED: 'false',
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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
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
                FIRST_PRESCRIPTION_VOUCHER_REDEEMED: 'false',
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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class UserRepeaterTest(TestCase):
    domain = 'bets-user-repeater'

    @classmethod
    def setUpClass(cls):
        super(UserRepeaterTest, cls).setUpClass()
        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()

        _, locations = setup_enikshay_locations(cls.domain)
        cls.private_location = locations['PCP']
        cls.private_location.metadata['private_sector_org_id'] = 'ORG_ID'
        cls.private_location.save()
        cls.dto_location = locations['DTO']
        cls.public_location = locations['DRTB-HIV']
        cls.test_location = locations['PAC']
        cls.test_location.metadata['is_test'] = "yes"
        cls.test_location.save()

        cls.repeater = BETSUserRepeater(
            domain=cls.domain,
            url='super-cool-url',
        )
        cls.repeater.save()

    @classmethod
    def tearDownClass(cls):
        super(UserRepeaterTest, cls).tearDownClass()
        cls.domain_obj.delete()
        delete_all_repeaters()

    def tearDown(self):
        super(UserRepeaterTest, self).tearDown()
        delete_all_repeat_records()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.utcnow())

    def make_user(self, location, user_data=None, username="davos.shipwright@stannis.gov"):
        user = CommCareUser.create(
            self.domain,
            username,
            "123",
            location=location,
            commit=False,
        )
        user.user_data['user_level'] = 'real'
        if user_data:
            user.user_data.update(user_data)
        user.save()
        self.addCleanup(user.delete)
        return user

    def test_real_private_user(self):
        self.make_user(self.private_location)
        records = self.repeat_records().all()
        self.assertEqual(1, len(records))

        self.assertDictContainsSubset(
            {'dtoLocation': self.dto_location.location_id,
             'privateSectorOrgId': self.private_location.metadata['private_sector_org_id']},
            json.loads(records[0].get_payload())
        )

    def test_private_user_payload(self):
        self.make_user(self.private_location, {'contact_phone_number': "911234567890"})
        record = self.repeat_records().all()[0]
        self.assertEqual(
            json.loads(record.get_payload())['default_phone_number'],
            "1234567890"
        )

    def test_public_user(self):
        self.make_user(self.public_location)
        self.assertEqual(0, len(self.repeat_records().all()))

    def test_test_user(self):
        self.make_user(self.test_location)
        self.assertEqual(0, len(self.repeat_records().all()))

    def test_updates(self):
        # saving a record multiple times shouldn't retrigger
        user = self.make_user(self.private_location)
        self.assertEqual(1, len(self.repeat_records().all()))
        user.save()
        self.assertEqual(1, len(self.repeat_records().all()))

        # modifying the record and saving it shouldn't retrigger if the record hasn't sent
        user = self.make_user(self.private_location, username="daenerys@targaryens.net")
        self.assertEqual(2, len(self.repeat_records().all()))
        record = list(self.repeat_records())[-1]
        user.first_name = "daenerys"
        user.save()
        self.assertEqual(2, len(self.repeat_records().all()))

        _mock_fire_record(record)
        # record gets taken out of queue
        self.assertEqual(1, len(self.repeat_records().all()))

        user = CommCareUser.get(user.user_id)
        self.assertEqual(
            user.user_data.get('BETS_user_repeat_record_ids'),
            record._id
        )
        # updating the user after a successful send, should add this user to the queue
        user.first_name = 'dani'
        user.save()
        self.assertEqual(2, len(self.repeat_records().all()))

        record = list(self.repeat_records())[-1]
        _mock_fire_record(record)

        # updating the id_device_number or id_device_body shouldn't trigger
        user = CommCareUser.get(user.user_id)
        user.user_data['id_device_body'] = "AA"
        user.user_data['id_device_number'] = 1
        user.save()
        self.assertEqual(1, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class LocationRepeaterTest(ENikshayLocationStructureMixin, TestCase):
    domain = 'bets-location-repeater'
    maxDiff = None

    def setUp(self):
        super(LocationRepeaterTest, self).setUp()
        self.repeater = BETSLocationRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.save()

    def tearDown(self):
        super(LocationRepeaterTest, self).tearDown()
        delete_all_repeat_records()
        delete_all_repeaters()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.utcnow())

    def make_location(self, name, location_type=None, metadata=None):
        location = SQLLocation.objects.create(
            domain=self.domain,
            name=name,
            site_code=name,
            location_type=location_type or self.tu.location_type,
            parent=self.dto,
            metadata=metadata or {},
        )
        self.addCleanup(location.delete)
        return location

    def test_trigger(self):
        self.assertEqual(0, len(self.repeat_records().all()))
        location = self.make_location('kings_landing')
        records = self.repeat_records().all()
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual(
            json.loads(record.get_payload()),
            {
                '_id': location.location_id,
                'ancestors_by_type': {
                    'dto': self.locations['DTO'].location_id,
                    'cto': self.locations['CTO'].location_id,
                    'sto': self.locations['STO'].location_id,
                    'ctd': self.locations['CTD'].location_id,
                },
                'doc_type': 'Location',
                'domain': self.domain,
                'external_id': None,
                'is_archived': False,
                'last_modified': location.last_modified.isoformat(),
                'latitude': None,
                'lineage': [
                    self.locations['DTO'].location_id,
                    self.locations['CTO'].location_id,
                    self.locations['STO'].location_id,
                    self.locations['CTD'].location_id,
                ],
                'location_id': location.location_id,
                'location_type': 'tu',
                'location_type_code': 'tu',
                'longitude': None,
                'metadata': {
                    'is_test': None,
                    'tests_available': None,
                    'private_sector_org_id': None,
                    'nikshay_code': None,
                    'enikshay_enabled': None,
                },
                'name': location.name,
                'parent_location_id': self.locations['DTO'].location_id,
                'parent_site_code': self.locations['DTO'].site_code,
                'site_code': location.site_code,
            }
        )

    def test_dont_send(self):
        # Don't send a PHI, as it's not relevant to the private sector
        location = self.make_location('sept_of_baelor', location_type=self.phi.location_type)
        # Don't send a test location
        location = self.make_location('flea_bottom', metadata={'is_test': 'yes'})
        self.assertEqual(0, len(self.repeat_records().all()))

        # saving a record multiple times shouldn't retrigger
        location = self.make_location('kings_landing')
        self.assertEqual(1, len(self.repeat_records().all()))
        location.save()
        self.assertEqual(1, len(self.repeat_records().all()))

        # modifying the record and saving it shouldn't retrigger if the record hasn't sent
        location = self.make_location('dorn')
        self.assertEqual(2, len(self.repeat_records().all()))
        record = list(self.repeat_records())[-1]
        location.metadata['private_sector_org_id'] = "new data!"
        location.save()
        self.assertEqual(2, len(self.repeat_records().all()))

        _mock_fire_record(record)
        self.assertEqual(1, len(self.repeat_records().all()))

        location = SQLLocation.objects.get(location_id=location.location_id)
        self.assertEqual(
            location.metadata.get('BETS_location_repeat_record_ids'),
            record._id
        )
        # updating the location after a successful send, should add this location to the queue
        location.metadata['private_sector_org_id'] = 'Woop!'
        location.save()
        self.assertEqual(2, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class BETSBeneficiaryRepeaterTest(ENikshayRepeaterTestBase):
    def setUp(self):
        super(BETSBeneficiaryRepeaterTest, self).setUp()
        self.domain_obj = Domain(name=self.domain)
        self.domain_obj.save()
        self.repeater = BETSBeneficiaryRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.save()

        loc_type = LocationType.objects.create(
            domain=self.domain,
            name="loc_type",
            administrative=True,
        )
        self.real_location = SQLLocation.objects.create(
            domain=self.domain,
            name="real_location",
            site_code="real_location",
            location_type=loc_type,
            metadata={'is_test': 'no', 'nikshay_code': 'nikshay_code'},
        )
        self.test_location = SQLLocation.objects.create(
            domain=self.domain,
            name="test_location",
            site_code="test_location",
            location_type=loc_type,
            metadata={'is_test': 'yes', 'nikshay_code': 'nikshay_code'},
        )

    def tearDown(self):
        super(BETSBeneficiaryRepeaterTest, self).tearDown()
        self.domain_obj.delete()

    def create_person_case(self, location_id, private=True):
        case = get_person_case_structure(None, self.episode_id)
        case.attrs['owner_id'] = location_id
        case.attrs['update']['current_episode_type'] = 'confirmed_tb'
        case.attrs['update']['contact_phone_number'] = '911234567890'
        case.attrs['update'][ENROLLED_IN_PRIVATE] = "true" if private else "false"
        return self.factory.create_or_update_cases([case])[0]

    def test_trigger(self):
        important_case_property = "phone_number"
        frivolous_case_property = "hair_color"

        # Create, then update test person case
        test_person = self.create_person_case(self.test_location.location_id)
        update_case(self.domain, test_person.case_id, {important_case_property: "7"})

        # Do the same for a public sector person case
        public_person = self.create_person_case(self.real_location.location_id, private=False)
        update_case(self.domain, public_person.case_id, {important_case_property: "7"})

        # None of the above should trigger forwarding
        self.assertEqual(0, len(self.repeat_records().all()))

        # Create real case
        real_person = self.create_person_case(self.real_location.location_id)
        records = self.repeat_records().all()
        self.assertEqual(1, len(records))
        payload = json.loads(records[0].get_payload())
        self.assertEqual(self.real_location.location_id, payload['properties']['owner_id'])
        # Update real case
        update_case(self.domain, real_person.case_id, {important_case_property: "7"})
        self.assertEqual(2, len(self.repeat_records().all()))
        # frivolous update shouldn't trigger another repeat
        update_case(self.domain, real_person.case_id, {frivolous_case_property: "blue"})
        self.assertEqual(2, len(self.repeat_records().all()))

    def test_payload(self):
        self.create_person_case(self.real_location.location_id)
        record = self.repeat_records().all()[0]
        payload = json.loads(record.get_payload())
        self.assertEqual(
            payload['properties']['phone_number'],
            '1234567890'  # "91" is removed
        )


def _mock_fire_record(record):
    mock_response_json = {
        "code": 200,
        "meta": {
            "failCount": "0",
            "successCount": "1",
            "totalCount": "1",
        },
        "response": [
            {
                "status": "Success",
                "failureDescription": ""
            }
        ]
    }
    with mock.patch('corehq.motech.repeaters.models.simple_post') as mock_post:
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json = mock.MagicMock(return_value=mock_response_json)
        mock_post.return_value = mock_response
        record.fire()
