from django.test.testcases import TestCase
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.callcenter.sync_usercase import sync_usercases
from corehq.apps.callcenter.tasks import bulk_sync_usercases_if_applicable

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType
from corehq.apps.locations.tests.util import make_loc
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.models import CommCareCase
from corehq.util.test_utils import privilege_enabled


@privilege_enabled(privileges.USERCASE)
class TestWebUserSyncUsercase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestWebUserSyncUsercase, cls).setUpClass()
        cls.username = "test-username"
        cls.commcare_username = "test-commcare-username"
        cls.domain_obj = create_domain("test")
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.domain_name = cls.domain_obj.name
        cls.user = WebUser.create(cls.domain_name, cls.username, '***', None, None)
        cls.commcare_user = CommCareUser.create(cls.domain_name, cls.commcare_username, '***',
                                                None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain_name, deleted_by=None)
        cls.user_id = cls.user._id

        LocationType.objects.get_or_create(
            domain=cls.domain_name,
            name='location-type',
        )
        cls.location = make_loc(
            'loc', type='location-type', domain='test'
        )
        cls.another_location = make_loc(
            code='another-loc', type='location-type', domain='test'
        )

    def _get_usercase_properties(self, user_id):
        return CommCareCase.objects.get_case_by_external_id(
            self.domain_name, user_id, USERCASE_TYPE
        ).case_json

    def test_sync_usercases(self):
        sync_usercases(self.user, self.domain_name)
        usercase = CommCareCase.objects.get_case_by_external_id(self.domain_name, self.user_id, USERCASE_TYPE)
        self.assertIsNotNone(usercase)
        self.assertEqual(usercase.name, self.username)

    def test_close_deactivated_web_users_usercase(self):
        sync_usercases(self.user, self.domain_name)
        init_usercase = CommCareCase.objects.get_case_by_external_id(self.domain_name, self.user_id, USERCASE_TYPE)
        self.assertFalse(init_usercase.closed)

        self.user.deactivate(self.domain_obj.name, self.user)
        closed_usercase = CommCareCase.objects.get_case_by_external_id(
            self.domain_name, self.user_id, USERCASE_TYPE)
        self.assertTrue(closed_usercase.closed)

        self.user.reactivate(self.domain_obj.name, self.user)
        open_usercase = CommCareCase.objects.get_case_by_external_id(self.domain_name, self.user_id, USERCASE_TYPE)
        self.assertFalse(open_usercase.closed)

    def test_location_data(self):
        self.user.set_location(self.domain_name, self.location)
        self.user.add_to_assigned_locations(self.domain_name, self.another_location)
        # usercase synced by save called during location updates
        usercase_case_properties = self._get_usercase_properties(self.user._id)
        self.assertEqual(usercase_case_properties['commcare_location_id'], self.location.location_id)
        self.assertEqual(usercase_case_properties['commcare_primary_case_sharing_id'], self.location.location_id)
        self.assertEqual(
            usercase_case_properties['commcare_location_ids'],
            ' '.join(self.user.get_location_ids(self.domain_name))
        )

        self.user.unset_location(self.domain_name)
        self.user.reset_locations(self.domain_name, [])
        # usercase synced by save called during location updates
        usercase_case_properties = self._get_usercase_properties(self.user._id)
        self.assertEqual(usercase_case_properties['commcare_location_id'], '')
        self.assertEqual(usercase_case_properties['commcare_primary_case_sharing_id'], '')
        self.assertEqual(usercase_case_properties['commcare_location_ids'], '')

    def test_location_data_for_commcare_user(self):
        self.commcare_user.set_location(self.location)
        self.commcare_user.add_to_assigned_locations(self.another_location)
        # usercase synced by save called during location updates
        usercase_case_properties = self._get_usercase_properties(self.commcare_user._id)
        self.assertEqual(usercase_case_properties['commcare_location_id'], self.location.location_id)
        self.assertEqual(usercase_case_properties['commcare_primary_case_sharing_id'], self.location.location_id)
        self.assertEqual(
            usercase_case_properties['commcare_location_ids'],
            ' '.join(self.commcare_user.get_location_ids(self.domain_name))
        )

        self.commcare_user.unset_location()
        self.commcare_user.reset_locations([])
        # usercase synced by save called during location updates
        usercase_case_properties = self._get_usercase_properties(self.commcare_user._id)
        self.assertEqual(usercase_case_properties['commcare_location_id'], '')
        self.assertEqual(usercase_case_properties['commcare_primary_case_sharing_id'], '')
        self.assertEqual(usercase_case_properties['commcare_location_ids'], '')


@privilege_enabled(privileges.USERCASE)
class TestBulkSyncUsercases(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestBulkSyncUsercases, cls).setUpClass()
        cls.domain_obj = create_domain("test")
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.domain_name = cls.domain_obj.name

        cls.users = []
        cls.user_ids = []
        cls.usernames = ['test1', 'test2', 'test3']

        # Create multiple users
        for username in cls.usernames:
            user = CommCareUser.create(cls.domain_name, username, '***', None, None)
            cls.users.append(user)
            cls.addClassCleanup(user.delete, cls.domain_name, deleted_by=None)
        # Get their ids
        for user in cls.users:
            cls.user_ids.append(user._id)

    def test_bulk_sync_usercases(self):
        bulk_sync_usercases_if_applicable(self.domain_name, self.user_ids)

        # Iterate through each id and assert cases properly synced
        for id in self.user_ids:
            usercase = CommCareCase.objects.get_case_by_external_id(self.domain_name, id, USERCASE_TYPE)
            self.assertIsNotNone(usercase)
            self.assertEqual(usercase.name, self.usernames.pop(0))
