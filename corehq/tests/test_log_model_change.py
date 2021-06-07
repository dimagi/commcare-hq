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
                                           action=ModelAction.CREATE.value)
        self.assertEqual(log_entry.object_type, "CommCareUser")
        self.assertEqual(log_entry.object_id, user1.get_id)
        self.assertEqual(log_entry.message, None)
        self.assertEqual(
            log_entry.details,
            {
                'changes': _get_user1_expected_log_entry_changes_json(user1),
                'changed_via': USER_CHANGE_VIA_WEB,
            }
        )
        user1_id = user1.get_id
        user1.delete(self.domain, web_user, USER_CHANGE_VIA_BULK_IMPORTER)
        log_entry = HQLogEntry.objects.get(domain=self.domain, by_user_id=web_user.get_id,
                                           action=ModelAction.DELETE.value)
        self.assertEqual(log_entry.object_type, "CommCareUser")
        self.assertEqual(log_entry.object_id, user1_id)
        self.assertEqual(log_entry.message, None)
        self.assertEqual(
            log_entry.details,
            {
                'changes': _get_user1_expected_log_entry_changes_json(user1),
                'changed_via': USER_CHANGE_VIA_BULK_IMPORTER,
            }
        )

    def test_system_admin_action(self):
        self.assertEqual(
            HQLogEntry.objects.filter(by_user_id=SYSTEM_USER_ID).count(),
            0
        )

        # create action with domain
        web_user = WebUser.create(self.domain, 'admin@test-domain.commcarehq.org', 'secret1',
                                  created_by=SYSTEM_USER_ID, created_via=__name__)

        log_entry = HQLogEntry.objects.get(by_user_id=SYSTEM_USER_ID, action=ModelAction.CREATE.value)
        self.assertEqual(log_entry.message, None)
        self.assertEqual(
            log_entry.details,
            {
                'changes': _get_web_user_expected_log_entry_changes_json(web_user),
                'changed_via': __name__,
            }
        )
        self.assertEqual(log_entry.object_id, web_user.get_id)

        web_user_id = web_user.get_id

        # domain less delete action
        web_user.delete(None, deleted_by=SYSTEM_USER_ID, deleted_via=__name__)
        log_entry = HQLogEntry.objects.get(by_user_id=SYSTEM_USER_ID, action=ModelAction.DELETE.value)
        self.assertEqual(log_entry.message, None)
        self.assertEqual(
            log_entry.details,
            {
                'changes': _get_web_user_expected_log_entry_changes_json(web_user),
                'changed_via': __name__,
            }
        )
        self.assertEqual(log_entry.object_id, web_user_id)

    def tearDown(self):
        delete_all_users()

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()


def _get_user1_expected_log_entry_changes_json(couch_user):
    user_json = couch_user.to_json()

    return {
        'CURRENT_VERSION': 3.0,
        'analytics_enabled': True,
        'announcements_seen': [],
        'assigned_location_ids': [],
        'attempt_date': None,
        'base_doc': 'CouchUser',
        'created_on': user_json['created_on'].split('.')[0],
        'date_joined': user_json['date_joined'].split('.')[0],
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
        'is_staff': False,
        'is_superuser': False,
        'language': None,
        'last_login': None,
        'last_modified': user_json['last_modified'].split('.')[0],
        'last_name': '',
        'loadtest_factor': None,
        'location_id': None,
        'login_attempts': 0,
        'phone_numbers': [],
        'registering_device_id': '',
        'status': None,
        'subscribed_to_commcare_users': False,
        'two_factor_auth_disabled_until': None,
        'user_data': {'commcare_project': 'test'},
        'user_location_id': None,
        'username': 'user@test-domain.commcarehq.org'
    }


def _get_web_user_expected_log_entry_changes_json(couch_user):
    user_json = couch_user.to_json()

    return {
        'CURRENT_VERSION': 3.0,
        'analytics_enabled': True,
        'announcements_seen': [],
        'assigned_location_ids': [],
        'attempt_date': None,
        'atypical_user': False,
        'base_doc': 'CouchUser',
        'created_on': user_json['created_on'].split('.')[0],
        'date_joined': user_json['date_joined'].split('.')[0],
        'doc_type': 'WebUser',
        'domain_memberships': [{
            'assigned_location_ids': [],
            'doc_type': 'DomainMembership',
            'domain': 'test',
            'is_admin': False,
            'last_accessed': None,
            'location_id': None,
            'override_global_tz': False,
            'program_id': None,
            'role_id': None,
            'timezone': 'UTC'
        }],
        'domains': ['test'],
        'email': '',
        'eulas': [],
        'fcm_device_token': None,
        'first_name': '',
        'has_built_app': False,
        'is_active': True,
        'is_staff': False,
        'is_superuser': False,
        'language': None,
        'last_login': None,
        'last_modified': user_json['last_modified'].split('.')[0],
        'last_name': '',
        'last_password_set': '1900-01-01T00:00:00',
        'location_id': None,
        'login_attempts': 0,
        'phone_numbers': [],
        'program_id': None,
        'status': None,
        'subscribed_to_commcare_users': False,
        'two_factor_auth_disabled_until': None,
        'user_data': {'commcare_project': 'test'},
        'username': 'admin@test-domain.commcarehq.org'
    }
