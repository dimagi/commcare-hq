from django.test.testcases import TestCase
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.callcenter.sync_usercase import sync_usercases

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
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
