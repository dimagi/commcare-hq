from datetime import datetime, timedelta

from django.test import TestCase
from django.test.client import RequestFactory
from django.test.utils import override_settings
from mock import MagicMock, patch

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports.standard.monitoring import WorkerActivityReport
from corehq.apps.users.models import WebUser
from dimagi.utils.dates import DateSpan


@override_settings(CACHE_REPORTS=True)
class ExportResponseTest(TestCase):
    domain = "export-response"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.request_factory = RequestFactory()
        cls.couch_user = WebUser.create(cls.domain, "export-response-test", "foobar", None, None)
        cls.couch_user.add_domain_membership(cls.domain, is_admin=True)
        cls.couch_user.save()

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_export_response_returns_200(self):
        request = self.request_factory.post('/some/url')
        request.couch_user = self.couch_user
        request.domain = self.domain
        request.datespan = DateSpan(
            startdate=datetime.utcnow() - timedelta(days=30),
            enddate=datetime.utcnow(),
        )
        request.can_access_all_locations = True

        report = WorkerActivityReport(request, domain=self.domain)
        report.rendered_as = 'export'
        res = report.export_response

        self.assertEqual(res.status_code, 200)

    @patch('corehq.apps.reports.standard.monitoring.WorkerActivityReport.export_table', MagicMock(return_value=[]))
    def test_export_response_returns_200_with_file(self):
        request = self.request_factory.post('/some/url')
        request.couch_user = self.couch_user
        request.domain = self.domain
        request.datespan = DateSpan(
            startdate=datetime.utcnow() - timedelta(days=30),
            enddate=datetime.utcnow(),
        )
        request.can_access_all_locations = True

        report = WorkerActivityReport(request, domain=self.domain)
        report.rendered_as = 'export'
        report.exportable_all = False
        res = report.export_response

        self.assertEqual(res.status_code, 200)

        expected_content_type = ('Content-Type', 'application/vnd.ms-excel')

        self.assertEqual(res._headers['content-type'], expected_content_type)

    @patch('corehq.apps.reports.standard.monitoring.WorkerActivityReport.export_table', return_value=[])
    @patch('corehq.apps.reports.generic.export_from_tables')
    def test_export_response_caches_file_response(self, export_from_tables_mock, _):
        # Only valid reports are cached and we need to pass
        # a path starting with /a/<domain> (see corehq.apps.reports.cache._is_valid)
        request = self.request_factory.post(f'/a/{self.domain}/report/url')
        request.couch_user = self.couch_user
        request.domain = self.domain
        request.datespan = DateSpan(
            startdate=datetime.utcnow() - timedelta(days=10),
            enddate=datetime.utcnow(),
        )
        request.can_access_all_locations = True

        report = WorkerActivityReport(request, domain=self.domain)
        report.rendered_as = 'export'
        report.exportable_all = False

        report.export_response
        report.export_response

        self.assertEqual(export_from_tables_mock.call_count, 1)

    @patch('corehq.apps.reports.generic.export_all_rows_task.delay')
    def test_export_response_does_not_cache_tasks(self, task_mock):
        request = self.request_factory.post(f'/a/{self.domain}/report/url')
        request.couch_user = self.couch_user
        request.domain = self.domain
        request.datespan = DateSpan(
            startdate=datetime.utcnow() - timedelta(days=30),
            enddate=datetime.utcnow(),
        )
        request.can_access_all_locations = True

        report = WorkerActivityReport(request, domain=self.domain)
        report.rendered_as = 'export'

        report.export_response
        report.export_response

        self.assertEqual(task_mock.call_count, 2)
