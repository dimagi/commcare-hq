import json

from django.test import TestCase

from django.contrib.admin.models import ADDITION
from corehq.apps.users.model_log import UserModelAction
from corehq.apps.users.util import _get_changed_details
from corehq.apps.users.management.commands.migrate_user_history_to_new_structure import \
    migrate_user_history_to_log_entry
from corehq.const import USER_CHANGE_VIA_WEB
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import UserHistory, WebUser, CommCareUser


class TestMigrateUserHistoryRecords(TestCase):
    domain = "test-domain"

    @classmethod
    def setUpClass(cls):
        cls.project = create_domain(cls.domain)
        cls.web_user = WebUser.create(cls.domain, 'test@commcarehq.org', '******',
                                      created_by=None, created_via=None)

    @classmethod
    def tearDownClass(cls):
        cls.web_user.delete(cls.domain, deleted_by=None)
        cls.project.delete()

    def test_migrate_user_history_to_log_entry(self):
        commcare_user = CommCareUser.create(self.domain, f'test@{self.domain}.commcarehq.org', '******',
                                            created_by=self.web_user, created_via=USER_CHANGE_VIA_WEB)
        user_change_details = _get_changed_details(commcare_user, UserModelAction.CREATE, {})
        user_history = UserHistory.objects.create(
            by_domain=self.domain,
            for_domain=self.domain,
            user_type=commcare_user.doc_type,
            user_id=commcare_user.get_id,
            changed_by=self.web_user.get_id,
            details={
                'changes': user_change_details,
                'changed_via': USER_CHANGE_VIA_WEB,
            },
            message="Password Reset",
            action=UserModelAction.CREATE.value
        )
        self.addCleanup(commcare_user.delete, self.domain, deleted_by=None)
        self.addCleanup(user_history.delete)

        log_entry = migrate_user_history_to_log_entry(user_history)

        self.assertEqual(log_entry.user_id, self.web_user.get_django_user().pk)
        self.assertEqual(log_entry.object_id, str(commcare_user.get_django_user().pk))
        self.assertEqual(log_entry.action_flag, ADDITION)
        self.assertEqual(log_entry.action_time, user_history.changed_at)

        change_message = json.loads(log_entry.change_message)
        self.assertEqual(change_message['details']['changed_via'], USER_CHANGE_VIA_WEB)
        self.assertEqual(change_message['details']['changes'], user_change_details)
        self.assertEqual(change_message['message'], "Password Reset")
        self.assertEqual(change_message['user_history_pk'], user_history.pk)
