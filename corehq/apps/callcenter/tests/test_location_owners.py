from django.test import TestCase

from casexml.apps.case.tests.util import delete_all_cases

from corehq.apps.callcenter.sync_usercase import sync_usercases
from corehq.apps.domain.models import CallCenterProperties
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType
from corehq.apps.locations.tests.util import make_loc
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase

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
        # Create domain
        cls.domain = create_domain(TEST_DOMAIN)
        cls.domain.call_center_config = cls.get_call_center_config()
        cls.domain.save()

        # Create user
        cls.user = CommCareUser.create(TEST_DOMAIN, 'user1', '***', None, None)

        # Create locations
        LocationType.objects.get_or_create(
            domain=cls.domain.name,
            name=LOCATION_TYPE,
        )
        cls.root_location = make_loc(
            'root_loc', type=LOCATION_TYPE, domain=TEST_DOMAIN
        )
        cls.child_location = make_loc(
            'child_loc', type=LOCATION_TYPE, domain=TEST_DOMAIN, parent=cls.root_location
        )
        cls.grandchild_location = make_loc(
            'grandchild_loc', type=LOCATION_TYPE, domain=TEST_DOMAIN, parent=cls.child_location
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()

    def tearDown(self):
        delete_all_cases()

    def test_no_location_sync(self):
        self.user.unset_location()
        sync_usercases(self.user, self.domain.name)
        self.assertCallCenterCaseOwner("")

    def test_location_sync(self):
        self.user.set_location(self.root_location)
        self.assertCallCenterCaseOwner(self.root_location._id)

    def test_location_change_sync(self):
        self.user.set_location(self.root_location)

        # Test changing to another location
        self.user.set_location(self.child_location)
        self.assertCallCenterCaseOwner(self.child_location._id)

        # Test changing to no location
        self.user.unset_location()
        self.assertCallCenterCaseOwner("")

    def test_ancestor_location_sync(self):
        # Alter config
        original_setting = self.domain.call_center_config.user_location_ancestor_level
        self.domain.call_center_config.user_location_ancestor_level = 2
        self.domain.save()

        self.user.set_location(self.grandchild_location)
        self.assertCallCenterCaseOwner(self.root_location._id)

        self.user.unset_location()
        # Call center case owner should be "" if the user's location is not set
        self.assertCallCenterCaseOwner("")

        self.user.set_location(self.child_location)
        # owner should be the highest ancestor if there aren't any further ancestors
        self.assertCallCenterCaseOwner(self.root_location._id)

        # Reset config
        self.domain.call_center_config.user_location_ancestor_level = original_setting
        self.domain.save()

    def assertCallCenterCaseOwner(self, owner_id):
        case = CommCareCase.objects.get_case_by_external_id(TEST_DOMAIN, self.user._id, CASE_TYPE)
        self.assertEqual(case.owner_id, owner_id)
