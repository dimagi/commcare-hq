from django.test import TestCase, override_settings

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.model_log import UserModelAction
from corehq.apps.users.models import CommCareUser, UserHistory, WebUser
from corehq.apps.users.util import SYSTEM_USER_ID, log_user_change, user_id_to_username
from corehq.const import USER_CHANGE_VIA_BULK_IMPORTER, USER_CHANGE_VIA_WEB


class TestLogUserChange(TestCase):
    domain = "test"
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.project = create_domain(cls.domain)
        cls.web_user = WebUser.create(cls.domain, 'test@commcarehq.org', '******',
                                      created_by=None, created_via=None)
        cls.commcare_user = CommCareUser.create(cls.domain, f'test@{cls.domain}.commcarehq.org', '******',
                                                created_by=cls.web_user, created_via=USER_CHANGE_VIA_WEB)

    @classmethod
    def tearDownClass(cls):
        UserHistory.objects.all().delete()
        cls.commcare_user.delete(cls.domain, deleted_by=None, deleted_via=None)
        cls.web_user.delete(cls.domain, deleted_by=None, deleted_via=None)
        cls.project.delete()

    def test_create(self):
        user_history = UserHistory.objects.get(user_id=self.commcare_user.get_id,
                                               action=UserModelAction.CREATE.value)
        self.assertEqual(user_history.by_domain, self.domain)
        self.assertEqual(user_history.for_domain, self.domain)
        self.assertEqual(user_history.user_type, "CommCareUser")
        self.assertEqual(user_history.user_id, self.commcare_user.get_id)
        self.assertIsNotNone(user_history.changed_by)
        self.assertEqual(user_history.changed_by, self.web_user.get_id)
        self.assertEqual(user_history.changes, _get_expected_changes_json(self.commcare_user))
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_WEB)
        self.assertEqual(user_history.change_messages, {})
        self.assertEqual(user_history.action, UserModelAction.CREATE.value)
        self.assertEqual(user_history.user_repr, user_id_to_username(self.commcare_user.get_id))
        self.assertEqual(user_history.changed_by_repr, user_id_to_username(self.web_user.get_id))

    def test_update(self):
        restore_phone_numbers_to = self.commcare_user.to_json()['phone_numbers']

        self.commcare_user.add_phone_number("9999999999")

        change_messages = UserChangeMessage.phone_numbers_added(["9999999999"])
        user_history = log_user_change(
            self.domain,
            self.domain,
            self.commcare_user,
            self.web_user,
            changed_via=USER_CHANGE_VIA_BULK_IMPORTER,
            change_messages=change_messages,
            fields_changed={
                'phone_numbers': self.commcare_user.phone_numbers,
                'password': '******'
            },
            action=UserModelAction.UPDATE
        )

        self.assertEqual(user_history.by_domain, self.domain)
        self.assertEqual(user_history.for_domain, self.domain)
        self.assertEqual(user_history.user_type, "CommCareUser")
        self.assertIsNotNone(user_history.user_id)
        self.assertEqual(user_history.user_id, self.commcare_user.get_id)
        self.assertIsNotNone(user_history.changed_by)
        self.assertEqual(user_history.changed_by, self.web_user.get_id)
        self.assertEqual(user_history.changes, {'phone_numbers': ['9999999999']})
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_BULK_IMPORTER)
        self.assertEqual(user_history.change_messages, change_messages)
        self.assertEqual(user_history.action, UserModelAction.UPDATE.value)
        self.assertEqual(user_history.user_repr, user_id_to_username(self.commcare_user.get_id))
        self.assertEqual(user_history.changed_by_repr, user_id_to_username(self.web_user.get_id))

        self.commcare_user.phone_numbers = restore_phone_numbers_to

    @override_settings(UNIT_TESTING=False)
    def test_delete_missing_deleted_by(self):
        with self.assertRaisesMessage(ValueError, "Missing deleted_by"):
            self.commcare_user.delete(self.domain, deleted_by=None)

    def test_delete(self):
        user_to_delete = CommCareUser.create(self.domain, f'delete@{self.domain}.commcarehq.org', '******',
                                             created_by=None, created_via=None)
        user_to_delete_id = user_to_delete.get_id
        deleted_username = user_id_to_username(user_to_delete_id)
        user_to_delete.delete(self.domain, deleted_by=self.web_user, deleted_via=USER_CHANGE_VIA_WEB)

        user_history = UserHistory.objects.get(by_domain=self.domain, for_domain=self.domain,
                                               user_id=user_to_delete_id)
        self.assertEqual(user_history.by_domain, self.domain)
        self.assertEqual(user_history.for_domain, self.domain)
        self.assertEqual(user_history.user_type, "CommCareUser")
        self.assertEqual(user_history.changed_by, self.web_user.get_id)
        self.assertEqual(user_history.changes, _get_expected_changes_json(user_to_delete))
        self.assertEqual(user_history.changed_via, USER_CHANGE_VIA_WEB)
        self.assertEqual(user_history.change_messages, {})
        self.assertEqual(user_history.action, UserModelAction.DELETE.value)
        self.assertEqual(user_history.user_repr, deleted_username)
        self.assertEqual(user_history.changed_by_repr, user_id_to_username(self.web_user.get_id))

    def test_missing_by_domain(self):
        new_user = CommCareUser.create(self.domain, f'test-new@{self.domain}.commcarehq.org', '******',
                                       created_by=self.web_user, created_via=USER_CHANGE_VIA_WEB)
        new_user_id = new_user.get_id

        # domain less delete action by non-system user
        with self.assertRaisesMessage(ValueError, "missing 'by_domain' argument'"):
            new_user.delete(None, deleted_by=self.web_user, deleted_via=__name__)

        # domain less delete action by SYSTEM_USER_ID
        self.assertEqual(
            UserHistory.objects.filter(changed_by=SYSTEM_USER_ID).count(),
            0
        )

        new_user.delete(None, deleted_by=SYSTEM_USER_ID, deleted_via=__name__)

        user_history = UserHistory.objects.get(changed_by=SYSTEM_USER_ID, action=UserModelAction.DELETE.value)
        self.assertEqual(user_history.user_id, new_user_id)

    def test_missing_for_domain(self):
        with self.assertRaisesMessage(ValueError, "missing 'for_domain' argument'"):
            log_user_change(
                by_domain=self.commcare_user.domain,
                for_domain=None,
                couch_user=self.commcare_user,
                changed_by_user=self.web_user,
                changed_via=USER_CHANGE_VIA_WEB,
                action=UserModelAction.UPDATE,
            )


def _get_expected_changes_json(user):
    user_json = user.to_json()
    return {
        'CURRENT_VERSION': '3.0',
        'analytics_enabled': True,
        'announcements_seen': [],
        'assigned_location_ids': [],
        'attempt_date': None,
        'base_doc': 'CouchUser',
        'can_assign_superuser': False,
        'created_on': user_json['created_on'],
        'date_joined': user_json['date_joined'],
        'demo_restore_id': None,
        'doc_type': 'CommCareUser',
        'domain': 'test',
        'domain_membership': {
            'assigned_location_ids': [],
            'doc_type': 'DomainMembership',
            'domain': 'test',
            'is_active': True,
            'is_admin': False,
            'last_accessed': None,
            'location_id': None,
            'override_global_tz': False,
            'program_id': None,
            'role_id': None,
            'timezone': 'UTC'
        },
        'email': '',
        'eulas': [],
        'first_name': '',
        'has_built_app': False,
        'is_account_confirmed': True,
        'is_active': True,
        'is_demo_user': False,
        'is_loadtest_user': False,
        'is_staff': False,
        'is_superuser': False,
        'language': None,
        'last_login': None,
        'last_modified': user_json['last_modified'],
        'last_name': '',
        'loadtest_factor': None,
        'location_id': None,
        'login_attempts': 0,
        'phone_numbers': [],
        'registering_device_id': '',
        'status': None,
        'subscribed_to_commcare_users': False,
        'two_factor_auth_disabled_until': None,
        'user_data': {},
        'user_location_id': None,
        'username': user_json['username']
    }
