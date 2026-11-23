from dimagi.utils.couch.undo import soft_delete
from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.tests.utils import get_sample_data_source, get_sample_report_config
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.users.models import WebUser
from corehq.tests.util.forms import csrf_client, submit_form
from corehq.util.test_utils import flag_enabled


@flag_enabled('USER_CONFIGURABLE_REPORTS')
class TestDeleteReportView(TestCase):
    domain = 'test-delete-report-view'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = create_domain(cls.domain)
        cls.addClassCleanup(cls.project.delete)
        cls.admin = WebUser.create(cls.domain, 'delete-report-admin', 'password', None, None, is_admin=True)
        cls.addClassCleanup(cls.admin.delete, cls.domain, deleted_by=None)

    def setUp(self):
        self.report = ReportConfiguration(
            domain=self.domain,
            config_id='missing-data-source',
            title='Report',
            aggregation_columns=['doc_id'],
            columns=[],
            filters=[],
            configured_charts=[],
        )
        self.report.save()
        self.addCleanup(ReportConfiguration.get_db().delete_doc, self.report._id)
        self.url = reverse('delete_configurable_report', args=[self.domain, self.report._id])
        self.client.login(username='delete-report-admin', password='password')

    def _doc_type(self):
        return ReportConfiguration.get_db().get(self.report._id)['doc_type']

    def test_get_is_rejected(self):
        response = self.client.get(self.url)
        assert response.status_code == 405
        assert self._doc_type() == 'ReportConfiguration'

    def test_post_deletes_report(self):
        response = self.client.post(self.url)
        assert response.status_code == 302
        assert self._doc_type() == 'ReportConfiguration-Deleted'

    @flag_enabled('REPORT_BUILDER_BETA_GROUP')  # gives access to report builder reports
    def test_button_on_report_builder_report(self):
        data_source = get_sample_data_source()
        data_source.domain = self.domain
        data_source.save()
        self.addCleanup(data_source.delete)
        report = get_sample_report_config()
        report.domain = self.domain
        report.config_id = data_source._id
        report.report_meta.created_by_builder = True
        # Linked reports can be deleted but not edited, which shows the delete button
        report.report_meta.master_id = 'upstream-report-id'
        report.save()
        self.addCleanup(ReportConfiguration.get_db().delete_doc, report._id)
        client = csrf_client('delete-report-admin', 'password')
        page = client.get(reverse('configurable', args=[self.domain, report._id]))
        assert page.status_code == 200

        response = submit_form(client, page, 'Delete Report')

        assert response.status_code == 302
        assert response.url == reverse('reports_home', args=[self.domain])
        assert ReportConfiguration.get_db().get(report._id)['doc_type'] == 'ReportConfiguration-Deleted'


@flag_enabled('USER_CONFIGURABLE_REPORTS')
class TestUndeleteReportView(TestCase):
    domain = 'test-undelete-report-view'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = create_domain(cls.domain)
        cls.addClassCleanup(cls.project.delete)
        cls.admin = WebUser.create(cls.domain, 'undelete-report-admin', 'password', None, None, is_admin=True)
        cls.addClassCleanup(cls.admin.delete, cls.domain, deleted_by=None)
        cls.data_source = get_sample_data_source()
        cls.data_source.domain = cls.domain
        cls.data_source.save()
        cls.addClassCleanup(cls.data_source.delete)
        # Restoring a report rebuilds its data source's table
        cls.addClassCleanup(get_indicator_adapter(cls.data_source).drop_table)

    def setUp(self):
        self.report = get_sample_report_config()
        self.report.domain = self.domain
        self.report.config_id = self.data_source._id
        self.report.save()
        self.addCleanup(ReportConfiguration.get_db().delete_doc, self.report._id)
        soft_delete(self.report)
        self.url = reverse('undo_delete_configurable_report', args=[self.domain, self.report._id])
        self.client.login(username='undelete-report-admin', password='password')

    def _doc_type(self):
        return ReportConfiguration.get_db().get(self.report._id)['doc_type']

    def test_get_is_rejected(self):
        response = self.client.get(self.url)
        assert response.status_code == 405
        assert self._doc_type() == 'ReportConfiguration-Deleted'

    def test_post_restores_report(self):
        response = self.client.post(self.url)
        assert response.status_code == 302
        assert self._doc_type() == 'ReportConfiguration'
