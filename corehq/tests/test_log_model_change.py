from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.models_sql import HQLogEntry
from corehq.apps.users.util import SYSTEM_USER_ID
from corehq.const import USER_CHANGE_VIA_WEB, USER_CHANGE_VIA_BULK_IMPORTER
from corehq.util.model_log import ModelAction


class TestLogModelChange(TestCase):
    domain = "test"

    @classmethod
    def setUpClass(cls):
        cls.project = create_domain(cls.domain)

    def test_logs(self):
        web_user = WebUser.create(self.domain, 'admin@test-domain.commcarehq.org', 'secret1', None, None)
        user1 = CommCareUser.create(self.domain, 'user@test-domain.commcarehq.org', 'secret2', web_user,
                                    USER_CHANGE_VIA_WEB)
        log_entry = HQLogEntry.objects.get(domain=self.domain, by_user_id=web_user.get_id,
                                           action_flag=ModelAction.CREATE.value)
        self.assertEqual(log_entry.object_type, "CommCareUser")
        self.assertEqual(log_entry.object_id, user1.get_id)
        self.assertEqual(log_entry.message, f"created_via: {USER_CHANGE_VIA_WEB}")
        user1_id = user1.get_id
        user1.delete(self.domain, web_user, USER_CHANGE_VIA_BULK_IMPORTER)
        log_entry = HQLogEntry.objects.get(domain=self.domain, by_user_id=web_user.get_id,
                                           action_flag=ModelAction.DELETE.value)
        self.assertEqual(log_entry.object_type, "CommCareUser")
        self.assertEqual(log_entry.object_id, user1_id)
        self.assertEqual(log_entry.message, f"deleted_via: {USER_CHANGE_VIA_BULK_IMPORTER}")

    def test_system_admin_action(self):
        self.assertEqual(
            HQLogEntry.objects.filter(by_user_id=SYSTEM_USER_ID).count(),
            0
        )

        # create action with domain
        web_user = WebUser.create(self.domain, 'admin@test-domain.commcarehq.org', 'secret1',
                                  created_by=SYSTEM_USER_ID, created_via=__name__)

        log_entry = HQLogEntry.objects.get(by_user_id=SYSTEM_USER_ID, action_flag=ModelAction.CREATE.value)
        self.assertEqual(log_entry.message, f"created_via: {__name__}")
        self.assertEqual(log_entry.object_id, web_user.get_id)

        web_user_id = web_user.get_id

        # domain less delete action
        web_user.delete(None, deleted_by=SYSTEM_USER_ID, deleted_via=__name__)
        log_entry = HQLogEntry.objects.get(by_user_id=SYSTEM_USER_ID, action_flag=ModelAction.DELETE.value)
        self.assertEqual(log_entry.message, f"deleted_via: {__name__}")
        self.assertEqual(log_entry.object_id, web_user_id)

    def tearDown(self):
        delete_all_users()

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
