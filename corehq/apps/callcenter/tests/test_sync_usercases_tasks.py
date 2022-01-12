from django.test.testcases import TestCase
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.callcenter.sync_usercase import sync_usercases
from corehq.apps.callcenter.tasks import bulk_sync_usercases_if_applicable

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.util.test_utils import flag_enabled
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class TestWebUserSyncUsercase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestWebUserSyncUsercase, cls).setUpClass()
        cls.username = "test-username"
        cls.domain_obj = create_domain("test")
        cls.domain_name = cls.domain_obj.name
        cls.user = WebUser.create(cls.domain_name, cls.username, '***', None, None)
        cls.user_id = cls.user._id
        cls.domain_obj.usercase_enabled = True
        cls.domain_obj.save()
        cls.accessor = CaseAccessors(cls.domain_name)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain_name, deleted_by=None)
        cls.domain_obj.delete()
        return super(TestWebUserSyncUsercase, cls).tearDownClass()

    @flag_enabled('USH_USERCASES_FOR_WEB_USERS')
    def test_sync_usercases(self):
        sync_usercases(self.user, self.domain_name)
        usercase = self.accessor.get_case_by_domain_hq_user_id(self.user_id, USERCASE_TYPE)
        self.assertIsNotNone(usercase)
        self.assertEqual(usercase.name, self.username)


class TestBulkSyncUsercases(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestBulkSyncUsercases, cls).setUpClass()
        cls.domain_obj = create_domain("test")
        cls.domain_name = cls.domain_obj.name
        cls.domain_obj.usercase_enabled = True
        cls.domain_obj.save()

        cls.users = []
        cls.user_ids = []
        cls.usernames = ['test1', 'test2', 'test3']

        # Create multiple users
        for username in cls.usernames:
            cls.users.append(CommCareUser.create(cls.domain_name, username, '***', None, None))
        # Get their ids
        for user in cls.users:
            cls.user_ids.append(user._id)
        cls.accessor = CaseAccessors(cls.domain_name)

    @classmethod
    def tearDownClass(cls):
        for user in cls.users:
            user.delete(cls.domain_name, deleted_by=None)
        cls.domain_obj.delete()
        return super(TestBulkSyncUsercases, cls).tearDownClass()

    def test_bulk_sync_usercases(self):
        bulk_sync_usercases_if_applicable(self.domain_name, self.user_ids)

        # Iterate through each id and assert cases properly synced
        for id in self.user_ids:
            usercase = self.accessor.get_case_by_domain_hq_user_id(id, USERCASE_TYPE)
            self.assertIsNotNone(usercase)
            self.assertEqual(usercase.name, self.usernames.pop(0))
