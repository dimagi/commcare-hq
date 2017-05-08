import datetime
from django.test import override_settings, TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.users.models import CommCareUser
from corehq.apps.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from corehq.apps.repeaters.models import RepeatRecord

from custom.enikshay.integrations.bets.repeater_generators import ChemistBETSVoucherPayloadGenerator, \
    BETS180TreatmentPayloadGenerator, BETSSuccessfulTreatmentPayloadGenerator, \
    BETSDiagnosisAndNotificationPayloadGenerator, BETSAYUSHReferralPayloadGenerator
from custom.enikshay.integrations.bets.repeaters import ChemistBETSVoucherRepeater, BETS180TreatmentRepeater, \
    BETSDrugRefillRepeater, BETSSuccessfulTreatmentRepeater, BETSDiagnosisAndNotificationRepeater, \
    BETSAYUSHReferralRepeater, BETSUserRepeater, BETSLocationRepeater
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
        self.assign_person_to_location(self.phi.location_id)
        voucher = self.create_prescription_voucher({
            "voucher_type": "prescription",
            'state': 'not approved'
        })
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
        self.assign_person_to_location(self.phi.location_id)
        update_case(
            self.domain,
            self.episode_id,
            {
                'adherence_total_doses_taken': 150,
                'treatment_outcome': 'not_evaluated'
            },
        )
        case = cases[self.episode_id]
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
        self.assign_person_to_location(self.phi.location_id)
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
        cases = self.create_case_structure()
        self.assign_person_to_location(self.phi.location_id)
        update_case(
            self.domain,
            self.episode_id,
            {
                'treatment_outcome': 'not_evaluated'
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
        self.assign_person_to_location(self.phi.location_id)
        update_case(
            self.domain,
            self.episode_id,
            {
                'pending_registration': 'yes',
                'nikshay_registered': 'false',
            },
        )
        case = cases[self.episode_id]
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
        cases = self.create_case_structure()
        self.assign_person_to_location(self.phi.location_id)
        update_case(
            self.domain,
            self.episode_id,
            {'presumptive_referral_by_ayush': 'false', 'nikshay_registered': 'false'},
        )
        self.assertEqual(0, len(self.repeat_records().all()))

        # Meet trigger
        update_case(
            self.domain, self.episode_id, {"nikshay_registered": "true", 'presumptive_referral_by_ayush': "123"}
        )
        self.assertEqual(1, len(self.repeat_records().all()))

        # Make sure same case doesn't trigger event again
        payload_generator = BETSAYUSHReferralPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), cases[self.episode_id], None)
        update_case(self.domain, self.episode_id, {"nikshay_registered": "false"})
        update_case(self.domain, self.episode_id, {"nikshay_registered": "true"})
        self.assertEqual(1, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class BETSUserRepeaterTest(TestCase):
    domain = 'user-repeater'

    def setUp(self):
        super(BETSUserRepeaterTest, self).setUp()
        self.repeater = BETSUserRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.save()

    def tearDown(self):
        super(BETSUserRepeaterTest, self).tearDown()
        delete_all_repeat_records()
        delete_all_repeaters()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.datetime.utcnow())

    def make_user(self, username):
        user = CommCareUser.create(
            self.domain,
            "{}@{}.commcarehq.org".format(username, self.domain),
            "123",
        )
        self.addCleanup(user.delete)
        return user

    def test_trigger(self):
        self.assertEqual(0, len(self.repeat_records().all()))
        user = self.make_user("bselmy")
        records = self.repeat_records().all()
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual(
            record.get_payload(),
            {
                'id': user._id,
                'username': user.username,
                'first_name': '',
                'last_name': '',
                'default_phone_number': None,
                'user_data': {'commcare_project': self.domain},
                'groups': [],
                'phone_numbers': [],
                'email': '',
                'resource_uri': '/a/user-repeater/api/v0.5/user/{}/'.format(user._id),
            }
        )


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class BETSLocationRepeaterTest(TestCase):
    domain = 'location-repeater'

    def setUp(self):
        super(BETSLocationRepeaterTest, self).setUp()
        self.domain_obj = create_domain(self.domain)
        self.repeater = BETSLocationRepeater(
            domain=self.domain,
            url='super-cool-url',
        )
        self.repeater.save()
        self.location_type = LocationType.objects.create(
            domain=self.domain,
            name="city",
        )

    def tearDown(self):
        super(BETSLocationRepeaterTest, self).tearDown()
        delete_all_repeat_records()
        delete_all_repeaters()
        self.domain_obj.delete()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.datetime.utcnow())

    def make_location(self, name):
        location = SQLLocation.objects.create(
            domain=self.domain,
            name=name,
            site_code=name,
            location_type=self.location_type,
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
            record.get_payload(),
            {
                '_id': location.location_id,
                'doc_type': 'Location',
                'domain': self.domain,
                'external_id': None,
                'is_archived': False,
                'last_modified': location.last_modified.isoformat(),
                'latitude': None,
                'lineage': [],
                'location_id': location.location_id,
                'location_type': 'city',
                'longitude': None,
                'metadata': {},
                'name': location.name,
                'parent_location_id': None,
                'site_code': location.site_code,
            }
        )
