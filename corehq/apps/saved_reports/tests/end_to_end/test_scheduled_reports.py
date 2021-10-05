from django.test import TestCase
from django.core import mail
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import UserRole, Permissions, WebUser, CouchUser
from pillowtop.es_utils import initialize_index_and_mapping
from corehq.util.elastic import ensure_active_es, ensure_index_deleted
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO

from ...models import ReportNotification, ReportConfig


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
        es = ensure_active_es()
        super().setUpClass()

        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.reports_role = UserRole.create(cls.domain, 'Test Role', permissions=Permissions(
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

        cls.es = ensure_active_es()
        initialize_index_and_mapping(es, CASE_INDEX_INFO)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by_domain=None, deleted_by=None)
        cls.reports_role.delete()
        cls.domain_obj.delete()
        ensure_index_deleted(CASE_INDEX_INFO.index)
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
