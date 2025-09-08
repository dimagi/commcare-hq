from django.test.testcases import TestCase
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.callcenter.sync_usercase import sync_usercases
from corehq.apps.callcenter.tasks import bulk_sync_usercases_if_applicable

from corehq import privileges
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.models import CommCareCase


class TestWebUserSyncUsercase(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super(TestWebUserSyncUsercase, cls).setUpClass()
        cls.username = "test-username"
        cls.domain_obj = create_domain("test")
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.domain_name = cls.domain_obj.name
        cls.user = WebUser.create(cls.domain_name, cls.username, '***', None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain_name, deleted_by=None)
        cls.user_id = cls.user._id

        cls.setup_subscription(cls.domain_name, SoftwarePlanEdition.PRO)
        domain_has_privilege.clear(cls.domain_name, privileges.USERCASE)

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


class TestBulkSyncUsercases(TestCase, DomainSubscriptionMixin):
    @classmethod
    def setUpClass(cls):
        super(TestBulkSyncUsercases, cls).setUpClass()
        cls.domain_obj = create_domain("test")
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.domain_name = cls.domain_obj.name

        cls.users = []
        cls.user_ids = []
        cls.usernames = ['test1', 'test2', 'test3']

        cls.setup_subscription(cls.domain_name, SoftwarePlanEdition.PRO)
        domain_has_privilege.clear(cls.domain_name, privileges.USERCASE)

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
