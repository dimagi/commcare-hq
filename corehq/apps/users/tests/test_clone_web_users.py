from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from toggle.models import Toggle
from toggle.shortcuts import toggle_enabled

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.export.dbaccessors import _get_export_instance
from corehq.apps.export.models import ExportInstance, FormExportInstance
from corehq.apps.saved_reports.models import ReportConfig, ReportNotification
from corehq.apps.users.management.commands.clone_web_users import (
    copy_domain_memberships,
    transfer_exports,
    transfer_feature_flags,
    transfer_saved_reports,
    transfer_scheduled_reports,
)
from corehq.apps.users.models import WebUser
from corehq.const import USER_CHANGE_VIA_CLONE
from corehq.toggles import NAMESPACE_USER, TAG_INTERNAL, StaticToggle

TEST_TOGGLE = StaticToggle(
    'test_toggle',
    'This is for tests',
    TAG_INTERNAL,
    [NAMESPACE_USER],
)


class TestCloneWebUsers(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestCloneWebUsers, cls).setUpClass()
        cls.domain = 'initial-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.admin_user = WebUser.create(
            None,
            'gherceg@dimagi.com',
            User.objects.make_random_password(),
            None,
            'api',
            by_domain_required_for_log=False,
            email='gherceg@dimagi.com',
        )

    @classmethod
    def tearDownClass(cls):
        cls.admin_user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super(TestCloneWebUsers, cls).tearDownClass()

    def setUp(self):
        super(TestCloneWebUsers, self).setUp()
        self.old_user = WebUser.create(
            self.domain,
            'old-user@dimagi.com',
            User.objects.make_random_password(),
            self.admin_user,
            'api',
            email='old-user@dimagi.com',
        )

        self.new_user = WebUser.create(
            None,
            'new-user@dimagi.com',
            User.objects.make_random_password(),
            None,
            USER_CHANGE_VIA_CLONE,
            by_domain_required_for_log=False,
            email='new-user@dimagi.com',
        )

    def tearDown(self):
        self.old_user.delete(self.domain, deleted_by=None)
        self.new_user.delete(self.domain, deleted_by=None)
        super(TestCloneWebUsers, self).tearDown()

    def test_copy_domain_memberships(self):
        self.assertEqual(1, len(self.old_user.domain_memberships))
        self.assertEqual([], self.new_user.domain_memberships)

        copy_domain_memberships(self.old_user, self.new_user)

        self.assertEqual(len(self.old_user.domain_memberships), len(self.new_user.domain_memberships))

    def test_copy_domain_memberships_copies_roles(self):
        old_domain_membership = self.old_user.domain_memberships[0]
        old_domain_membership.role_id = 'abc123'

        copy_domain_memberships(self.old_user, self.new_user)

        new_domain_membership = self.new_user.domain_memberships[0]
        self.assertEqual('abc123', new_domain_membership.role_id)

    def test_copy_domain_memberships_copies_locations(self):
        old_domain_membership = self.old_user.domain_memberships[0]
        old_domain_membership.location_id = 'abc123'

        copy_domain_memberships(self.old_user, self.new_user)

        new_domain_membership = self.new_user.domain_memberships[0]
        self.assertEqual('abc123', new_domain_membership.location_id)

    def test_dry_run_copy_domain_memberships(self):
        self.assertEqual(1, len(self.old_user.domain_memberships))
        self.assertEqual([], self.new_user.domain_memberships)

        copy_domain_memberships(self.old_user, self.new_user, dry_run=True)

        self.assertEqual(0, len(self.new_user.domain_memberships))

    def test_transfer_exports(self):
        export = FormExportInstance(owner_id=self.old_user._id, domain=self.domain)
        export.save()
        self.addCleanup(export.delete)

        transfer_exports(self.old_user, self.new_user)

        export = _get_export_instance(ExportInstance, [self.domain])[0]
        self.assertEqual(export.owner_id, self.new_user._id)

    def test_dry_run_transfer_exports(self):
        export = FormExportInstance(owner_id=self.old_user._id, domain=self.domain)
        export.save()
        self.addCleanup(export.delete)

        transfer_exports(self.old_user, self.new_user, dry_run=True)

        export = _get_export_instance(ExportInstance, [self.domain])[0]
        self.assertNotEqual(export.owner_id, self.new_user._id)

    def test_transfer_scheduled_reports(self):
        scheduled_report = ReportNotification(owner_id=self.old_user._id, domain=self.domain)
        scheduled_report.save()
        expected_report_id = scheduled_report._id
        self.addCleanup(scheduled_report.delete)

        transfer_scheduled_reports(self.old_user, self.new_user)

        scheduled_report = ReportNotification.by_domain_and_owner(self.domain, self.new_user._id, stale=False)[0]
        self.assertEqual(expected_report_id, scheduled_report._id)
        self.assertEqual(self.new_user._id, scheduled_report.owner_id)

    def test_dry_run_transfer_scheduled_reports(self):
        scheduled_report = ReportNotification(owner_id=self.old_user._id, domain=self.domain)
        scheduled_report.save()
        expected_report_id = scheduled_report._id
        self.addCleanup(scheduled_report.delete)

        transfer_scheduled_reports(self.old_user, self.new_user, dry_run=True)

        scheduled_report = ReportNotification.by_domain_and_owner(self.domain, self.old_user._id, stale=False)[0]
        self.assertEqual(expected_report_id, scheduled_report._id)
        self.assertEqual(self.old_user._id, scheduled_report.owner_id)

    def test_transfer_saved_reports(self):
        saved_report = ReportConfig(
            name='test',
            owner_id=self.old_user._id,
            report_slug='worker_activity',
            report_type='project_report',
            domain=self.domain)
        saved_report.save()
        expected_report_id = saved_report._id
        self.addCleanup(saved_report.delete)
        transfer_saved_reports(self.old_user, self.new_user)

        saved_report = ReportConfig.by_domain_and_owner(self.domain, self.new_user._id, stale=False)[0]
        self.assertEqual(expected_report_id, saved_report._id)
        self.assertEqual(self.new_user._id, saved_report.owner_id)

    def test_dry_run_transfer_saved_reports(self):
        saved_report = ReportConfig(
            name='test',
            owner_id=self.old_user._id,
            report_slug='worker_activity',
            report_type='project_report',
            domain=self.domain)
        saved_report.save()
        expected_report_id = saved_report._id
        self.addCleanup(saved_report.delete)
        transfer_saved_reports(self.old_user, self.new_user, dry_run=True)

        saved_report = ReportConfig.by_domain_and_owner(self.domain, self.old_user._id, stale=False)[0]
        self.assertEqual(expected_report_id, saved_report._id)
        self.assertEqual(self.old_user._id, saved_report.owner_id)

    def test_transfer_feature_flags(self):
        toggle = Toggle(slug='test_toggle', enabled_users=[self.old_user.username])
        toggle.save()
        self.addCleanup(toggle.delete)

        self.assertTrue(toggle_enabled('test_toggle', self.old_user.username))
        self.assertFalse(toggle_enabled('test_toggle', self.new_user.username))

        mock_togglesbyname = {'TEST_TOGGLE': TEST_TOGGLE}
        with patch('corehq.toggles.all_toggles_by_name', return_value=mock_togglesbyname),\
             patch('corehq.apps.users.management.commands.clone_web_users.all_toggles_by_name',
                   return_value=mock_togglesbyname):
            transfer_feature_flags(self.old_user.username, self.new_user.username)

        self.assertFalse(toggle_enabled('test_toggle', self.old_user.username))
        self.assertTrue(toggle_enabled('test_toggle', self.new_user.username))

    def test_dry_run_transfer_feature_flags(self):
        toggle = Toggle(slug='test_toggle', enabled_users=[self.old_user.username])
        toggle.save()
        self.addCleanup(toggle.delete)

        self.assertTrue(toggle_enabled('test_toggle', self.old_user.username))
        self.assertFalse(toggle_enabled('test_toggle', self.new_user.username))

        mock_togglesbyname = {'TEST_TOGGLE': TEST_TOGGLE}
        with patch('corehq.toggles.all_toggles_by_name', return_value=mock_togglesbyname),\
             patch('corehq.apps.users.management.commands.clone_web_users.all_toggles_by_name',
                   return_value=mock_togglesbyname):
            transfer_feature_flags(self.old_user.username, self.new_user.username, dry_run=True)

        self.assertTrue(toggle_enabled('test_toggle', self.old_user.username))
        self.assertFalse(toggle_enabled('test_toggle', self.new_user.username))
