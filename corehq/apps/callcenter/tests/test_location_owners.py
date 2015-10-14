from django.test import TestCase
from casexml.apps.case.tests import delete_all_cases
from corehq.apps.callcenter.utils import sync_call_center_user_case
from corehq.apps.domain.models import CallCenterProperties
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import get_case_by_domain_hq_user_id
from corehq.apps.locations.models import LocationType
from corehq.apps.locations.tests import make_loc
from corehq.apps.users.models import CommCareUser

TEST_DOMAIN = "cc-location-owner-test-domain"
CASE_TYPE = "cc-case-type"
LOCATION_TYPE = "my-location"


class CallCenterLocationOwnerTest(TestCase):

    @classmethod
    def get_call_center_config(cls):
        return CallCenterProperties(
            enabled=True,
            use_user_location_as_owner=True,
            case_owner_id=None,
            case_type=CASE_TYPE
        )

    @classmethod
    def setUpClass(cls):
        cls.domain = create_domain(TEST_DOMAIN)
        user = CommCareUser.create(TEST_DOMAIN, 'user1', '***')
        cls.user_id = user.user_id
        cls.domain.call_center_config = cls.get_call_center_config()
        cls.domain.save()

        LocationType.objects.get_or_create(
            domain=cls.domain.name,
            name=LOCATION_TYPE,
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()

    def setUp(self):
        self.user = CommCareUser.get(self.user_id)

    def tearDown(self):
        delete_all_cases()

    def test_no_location_sync(self):
        self.user.unset_location()
        self.user.save()
        sync_call_center_user_case(self.user)
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertEqual(case.owner_id, "")

    def test_location_sync(self):
        location = make_loc('loc', type=LOCATION_TYPE, domain=TEST_DOMAIN)
        self.user.set_location(location)
        self.user.save()
        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertEqual(case.owner_id, location._id)

    def test_location_change_sync(self):
        location = make_loc('loc', type=LOCATION_TYPE, domain=TEST_DOMAIN)
        self.user.set_location(location)
        self.user.save()
        location_2 = make_loc('loc2', type=LOCATION_TYPE, domain=TEST_DOMAIN)
        self.user.set_location(location_2)
        self.user.save()

        case = get_case_by_domain_hq_user_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertEqual(case.owner_id, location_2._id)
