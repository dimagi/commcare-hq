from unittest.mock import patch

from django.core import mail
from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import (
    CouchUser,
    HqPermissions,
    UserRole,
    WebUser,
)

from ...models import ReportConfig, ReportNotification


@patch('corehq.apps.reports.standard.monitoring.util.get_simplified_users',
       new=lambda q: [])
@es_test(requires=[case_adapter, form_adapter], setup_class=True)
class TestScheduledReports(TestCase):

    def test_scheduled_reports_sends_to_recipients(self):
        saved_report = self.create_saved_report()
        scheduled_report = self.create_scheduled_report([saved_report], ['test1@dimagi.com', 'test2@dimagi.com'])
        scheduled_report.send()

        recipients = {', '.join(email.recipients()) for email in mail.outbox}
        self.assertSetEqual(recipients, {'test1@dimagi.com', 'test2@dimagi.com'})

    # ******* Setup / Helpers

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.reports_role = UserRole.create(cls.domain, 'Test Role', permissions=HqPermissions(
            view_reports=True
        ))
        cls.user = cls.create_fresh_user(
            username='dummy@example.com',
            domain=cls.domain,
            password='secret',
            created_by=None,
            created_via=None,
            role_id=cls.reports_role.couch_id
        )

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by_domain=None, deleted_by=None)
        cls.reports_role.delete()
        cls.domain_obj.delete()
        super().tearDownClass()

    @classmethod
    def create_fresh_user(cls, username, **kwargs):
        try:
            user = WebUser.create(username=username, **kwargs)
        except CouchUser.Inconsistent:
            user = WebUser.get_by_username(username)
            user.delete(deleted_by_domain=None, deleted_by=None)
            user = WebUser.create(username=username, **kwargs)

        return user

    def create_saved_report(self):
        saved_report = ReportConfig(
            date_range='last30',
            days=30,
            domain=self.domain,
            report_slug='worker_activity',
            report_type='project_report',
            owner_id=self.user._id
        )
        saved_report.save()
        self.addCleanup(saved_report.delete)

        return saved_report

    def create_scheduled_report(self, saved_reports, emails):
        ids = [saved_report._id for saved_report in saved_reports]
        scheduled_report = ReportNotification(
            domain=self.domain, hour=12, minute=None, day=30, interval='monthly', config_ids=ids,
            owner_id=self.user._id, recipient_emails=emails
        )
        scheduled_report.save()
        self.addCleanup(scheduled_report.delete)

        return scheduled_report
