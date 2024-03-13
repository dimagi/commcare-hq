from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from couchdbkit.schema.base import DocumentBase

from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    Invitation,
    WebUser,
    DeviceAppMeta,
    HqPermissions,
)

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain


class CouchUserTest(SimpleTestCase):

    def test_web_user_flag(self):
        self.assertTrue(WebUser().is_web_user())
        self.assertTrue(CouchUser.wrap(WebUser().to_json()).is_web_user())
        self.assertFalse(CommCareUser().is_web_user())
        self.assertFalse(CouchUser.wrap(CommCareUser().to_json()).is_web_user())
        with self.assertRaises(NotImplementedError):
            CouchUser().is_web_user()

    def test_commcare_user_flag(self):
        self.assertFalse(WebUser().is_commcare_user())
        self.assertFalse(CouchUser.wrap(WebUser().to_json()).is_commcare_user())
        self.assertTrue(CommCareUser().is_commcare_user())
        self.assertTrue(CouchUser.wrap(CommCareUser().to_json()).is_commcare_user())
        with self.assertRaises(NotImplementedError):
            CouchUser().is_commcare_user()


class InvitationTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(InvitationTest, cls).setUpClass()
        cls.invitations = [
            Invitation(domain='domain_1', email='email1@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow()),
            Invitation(domain='domain_1', email='email1@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow(), is_accepted=True),
            Invitation(domain='domain_1', email='email2@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow(), is_accepted=True),
            Invitation(domain='domain_2', email='email3@email.com', invited_by='friend@email.com',
                       invited_on=datetime.utcnow()),
        ]
        for inv in cls.invitations:
            inv.save()

    def test_by_domain(self):
        self.assertEqual(len(Invitation.by_domain('domain_1')), 1)
        self.assertEqual(len(Invitation.by_domain('domain_1', is_accepted=True)), 2)
        self.assertEqual(len(Invitation.by_domain('domain_2')), 1)
        self.assertEqual(len(Invitation.by_domain('domain_3')), 0)

    def test_by_email(self):
        self.assertEqual(len(Invitation.by_email('email1@email.com')), 1)
        self.assertEqual(len(Invitation.by_email('email3@email.com')), 1)
        self.assertEqual(len(Invitation.by_email('email4@email.com')), 0)

    @classmethod
    def tearDownClass(cls):
        for inv in cls.invitations:
            inv.delete()
        super(InvitationTest, cls).tearDownClass()


class User_MessagingDomain_Tests(SimpleTestCase):
    def test_web_user_with_no_messaging_domain_returns_false(self):
        user = WebUser(domains=['domain_no_messaging_1', 'domain_no_messaging_2'])
        self.assertFalse(user.belongs_to_messaging_domain())

    def test_web_user_with_messaging_domain_returns_true(self):
        user = WebUser(domains=['domain_no_messaging_1', 'domain_with_messaging', 'domain_no_messaging_2'])
        self.assertTrue(user.belongs_to_messaging_domain())

    def test_commcare_user_is_compatible(self):
        user = CommCareUser(domain='domain_no_messaging_1')
        self.assertFalse(user.belongs_to_messaging_domain())

    def setUp(self):
        self.domains = {
            'domain_no_messaging_1': Domain(granted_messaging_access=False),
            'domain_no_messaging_2': Domain(granted_messaging_access=False),
            'domain_with_messaging': Domain(granted_messaging_access=True),
        }

        patcher = patch.object(Domain, 'get_by_name', side_effect=self._get_domain_by_name)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _get_domain_by_name(self, name):
        return self.domains[name]


class DeviceAppMetaMergeTests(SimpleTestCase):
    def test_overwrites_key(self):
        self.original_meta.num_unsent_forms = 5
        self.updates_meta.num_unsent_forms = 2

        self.original_meta.merge(self.updates_meta)
        self.assertEqual(self.original_meta.num_unsent_forms, 2)

    def test_ignores_older_submissions(self):
        recent_meta = DeviceAppMeta(num_unsent_forms=5, last_request=self.current_time)
        older_meta = DeviceAppMeta(num_unsent_forms=2, last_request=self.previous_time)

        recent_meta.merge(older_meta)
        self.assertEqual(recent_meta.num_unsent_forms, 5)

    def test_ignores_simultaneous_submissions(self):
        meta1 = DeviceAppMeta(num_unsent_forms=5, last_request=self.current_time)
        meta2 = DeviceAppMeta(num_unsent_forms=2, last_request=self.current_time)

        meta1.merge(meta2)
        self.assertEqual(meta1.num_unsent_forms, 5)

    def test_merges_new_properties(self):
        self.updates_meta.num_unsent_forms = 5

        self.original_meta.merge(self.updates_meta)
        self.assertEqual(self.original_meta.num_unsent_forms, 5)

    def test_merges_new_dates(self):
        self.updates_meta.last_heartbeat = self.current_time

        self.original_meta.merge(self.updates_meta)
        self.assertEqual(self.original_meta.last_heartbeat, self.current_time)

    def test_does_not_overwrite_unspecified_properties(self):
        self.original_meta.num_unsent_forms = 5

        self.original_meta.merge(self.updates_meta)
        self.assertEqual(self.original_meta.num_unsent_forms, 5)

    def test_uses_nontruthy_values(self):
        self.original_meta.num_unsent_forms = 5
        self.updates_meta.num_unsent_forms = 0

        self.original_meta.merge(self.updates_meta)
        self.assertEqual(self.original_meta.num_unsent_forms, 0)

    def test_updates_dates(self):
        self.original_meta.last_heartbeat = self.previous_time
        self.updates_meta.last_heartbeat = self.current_time

        self.original_meta.merge(self.updates_meta)
        self.assertEqual(self.original_meta.last_heartbeat, self.current_time)

    def test_ignores_older_dates(self):
        self.original_meta.num_unsent_forms = 5
        self.original_meta.last_heartbeat = self.current_time

        self.updates_meta.num_unsent_forms = 2
        self.updates_meta.last_heartbeat = self.previous_time

        self.original_meta.merge(self.updates_meta)
        self.assertEqual(self.original_meta.num_unsent_forms, 2)  # Normal values should still merge
        # But the older time should be ignored
        self.assertEqual(self.original_meta.last_heartbeat, self.current_time)

    def test_updates_last_request(self):
        original_meta = DeviceAppMeta(last_request=self.previous_time)
        updates_meta = DeviceAppMeta(last_heartbeat=self.current_time)

        original_meta.merge(updates_meta)
        self.assertEqual(original_meta.last_request, self.current_time)

    def setUp(self):
        self.previous_time = datetime(2022, 10, 2)
        self.current_time = self.previous_time + timedelta(hours=1)

        self.original_meta = DeviceAppMeta(last_request=self.previous_time)
        self.updates_meta = DeviceAppMeta(last_request=self.current_time)


class DeviceAppMetaLatestRequestTests(SimpleTestCase):
    def test_uses_max_from_submission(self):
        meta = DeviceAppMeta(
            last_submission=self.current_time,
            last_sync=self.previous_time,
            last_heartbeat=self.previous_time
        )
        meta._update_latest_request()
        self.assertEqual(meta.last_request, self.current_time)

    def test_uses_max_from_sync(self):
        meta = DeviceAppMeta(
            last_sync=self.current_time,
            last_submission=self.previous_time,
            last_heartbeat=self.previous_time
        )
        meta._update_latest_request()
        self.assertEqual(meta.last_request, self.current_time)

    def test_uses_max_from_heartbeat(self):
        meta = DeviceAppMeta(
            last_heartbeat=self.current_time,
            last_submission=self.previous_time,
            last_sync=self.previous_time
        )
        meta._update_latest_request()
        self.assertEqual(meta.last_request, self.current_time)

    def setUp(self):
        self.previous_time = datetime(2022, 10, 2)
        self.current_time = self.previous_time + timedelta(hours=1)


class HQPermissionsTests(SimpleTestCase):
    def test_normalize_removes_permissions_from_location_restricted_user(self):
        permissions = HqPermissions(
            edit_web_users=True,
            view_web_users=True,
            edit_groups=True,
            view_groups=True,
            edit_apps=True,
            view_roles=True,
            edit_reports=True,
            edit_billing=True
        )
        permissions.access_all_locations = False

        permissions.normalize()

        self.assertFalse(permissions.edit_web_users)
        self.assertFalse(permissions.view_web_users)
        self.assertFalse(permissions.edit_groups)
        self.assertFalse(permissions.view_groups)
        self.assertFalse(permissions.edit_apps)
        self.assertFalse(permissions.view_roles)
        self.assertFalse(permissions.edit_reports)
        self.assertFalse(permissions.edit_billing)

    def test_normalize_edit_users_implies_view_users(self):
        permissions = HqPermissions(edit_web_users=True, view_web_users=False)
        permissions.normalize()

        self.assertTrue(permissions.view_web_users)

    def test_normalize_edit_commcare_users_implies_view_users(self):
        permissions = HqPermissions(edit_commcare_users=True, view_commcare_users=False)
        permissions.normalize()

        self.assertTrue(permissions.view_commcare_users)

    def test_normalize_edit_group_implies_view_group(self):
        permissions = HqPermissions(edit_groups=True, view_groups=False)
        permissions.normalize()

        self.assertTrue(permissions.view_groups)

    def test_normalize_disabled_edit_groups_prevents_editing_users_in_groups(self):
        permissions = HqPermissions(edit_groups=False, edit_users_in_groups=True)
        permissions.normalize()

        self.assertFalse(permissions.edit_users_in_groups)

    def test_normalize_edit_locations_implies_viewing_locations(self):
        permissions = HqPermissions(edit_locations=True, view_locations=False)
        permissions.normalize()

        self.assertTrue(permissions.view_locations)

    def test_normalize_disabled_edit_locations_prevents_editing_users_locations(self):
        permissions = HqPermissions(edit_locations=False, edit_users_in_locations=True)
        permissions.normalize()

        self.assertFalse(permissions.edit_users_in_locations)

    def test_normalize_edit_apps_implies_view_apps(self):
        permissions = HqPermissions(edit_apps=True, view_apps=False)
        permissions.normalize()

        self.assertTrue(permissions.view_apps)

    def test_normalize_access_release_management_preserves_previous_edit_linked_config_value(self):
        permissions = HqPermissions(access_release_management=True, edit_linked_configurations=True)
        old_permissions = HqPermissions(edit_linked_configurations=False)
        permissions.normalize(previous=old_permissions)

        self.assertFalse(permissions.edit_linked_configurations)

    def test_normalize_disabled_release_management_uses_edit_linked_config_value(self):
        permissions = HqPermissions(access_release_management=False, edit_linked_configurations=True)
        old_permissions = HqPermissions(edit_linked_configurations=False)
        permissions.normalize(previous=old_permissions)

        self.assertTrue(permissions.edit_linked_configurations)

    def test_diff_returns_an_empty_list_for_matching_permissions(self):
        left = HqPermissions(edit_apps=True, view_apps=True)
        right = HqPermissions(edit_apps=True, view_apps=True)
        self.assertEqual(HqPermissions.diff(left, right), [])

    def test_diff_builds_array_of_mismatched_permission_names(self):
        left = HqPermissions(view_report_list=['report1'])
        right = HqPermissions(view_report_list=['report2'])
        self.assertEqual(HqPermissions.diff(left, right), ['view_reports'])

    def test_diff_includes_missing_permissions_from_left(self):
        left = HqPermissions()
        right = HqPermissions(view_reports=True)
        self.assertEqual(HqPermissions.diff(left, right), ['view_reports'])

    def test_diff_includes_missing_permissions_from_right(self):
        left = HqPermissions(view_reports=True)
        right = HqPermissions()
        self.assertEqual(HqPermissions.diff(left, right), ['view_reports'])


class CouchUserSaveRaceConditionTests(TestCase):

    def test_couch_user_save_race_condition(self):
        """
        WebUser and CommCareUser use the same underlying save method that is being tested here
        """
        username = 'race-test-user@test.com'
        user = WebUser.create(self.domain.name, username, '***', None, None)
        self.addCleanup(user.delete, None, deleted_by=None)

        rev_before = WebUser.get_by_username(username)._rev
        super_save = DocumentBase.save

        def race_save(self, *args, **kw):
            """
            Simulate a scenario where another process calls get_by_username while the current process is executing
            user.save(). The call happens after user.save() is called, but prior to the user object actually being
            saved to Couch (prior to super().save() being called)
            """
            WebUser.get_by_username(username)
            return super_save(self, *args, **kw)

        with patch.object(DocumentBase, "save", race_save):
            user.save()

        rev_after = WebUser.get_by_username(username)._rev
        diff = int(rev_after.split('-')[0]) - int(rev_before.split('-')[0])
        self.assertEqual(diff, 1)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain('race-user-test')
        cls.addClassCleanup(cls.domain.delete)
