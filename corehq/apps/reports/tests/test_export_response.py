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
        cls.couch_user.delete(deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_export_response_returns_200(self):
        request = self.request_factory.post(f'/{self.domain}/reports/export/worker_activity')
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
        request = self.request_factory.post(f'/{self.domain}/reports/expt/worker_activity')
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
