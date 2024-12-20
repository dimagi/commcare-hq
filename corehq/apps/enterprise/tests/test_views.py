from django.test import SimpleTestCase, TestCase, RequestFactory
from datetime import datetime
from importlib import reload
from unittest.mock import patch

from corehq.apps.accounting.tests.generator import billing_account
from corehq.apps.enterprise import views
from corehq.apps.enterprise.enterprise import EnterpriseReport

from corehq.apps.enterprise import decorators as enterprise_decorators
from corehq.apps.domain import decorators as domain_decorators

from corehq.apps.users.models import WebUser

from codecs import BOM_UTF8


class EnterpriseDashboardDownloadTests(SimpleTestCase):
    def test_bom_is_inserted_at_start_of_file(self):
        request = RequestFactory().get('/')
        self.mock_get_export_content.return_value = '1234'

        response = views.enterprise_dashboard_download(request, 'test-domain', 'test-report', 'some-hash-id')
        self.assertEqual(response.content, BOM_UTF8 + b'1234')

    def test_mimetype_is_set_to_csv(self):
        request = RequestFactory().get('/')
        response = views.enterprise_dashboard_download(request, 'test-domain', 'test-report', 'some-hash-id')

        self.assertEqual(response.headers['Content-Type'], 'text/csv; charset=UTF-8')

    def test_filename_is_set_correctly(self):
        request = RequestFactory().get('/')
        self.mock_get_filename.return_value = 'myreport.csv'

        response = views.enterprise_dashboard_download(request, 'test-domain', 'test-report', 'some-hash-id')

        self.assertEqual(response.headers['Content-Disposition'], 'attachment; filename="myreport.csv"')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._patch_decorators()
        reload(views)

    def setUp(self):
        filename_patcher = patch.object(views, '_get_export_filename', return_value='test_file.csv')
        self.mock_get_filename = filename_patcher.start()
        self.addCleanup(filename_patcher.stop)

        content_patcher = patch.object(views, '_get_export_content', return_value='some_content')
        self.mock_get_export_content = content_patcher.start()
        self.addCleanup(content_patcher.stop)

    @classmethod
    def _patch_decorators(cls):
        require_enterprise_admin_patcher = patch.object(
            enterprise_decorators, 'require_enterprise_admin', lambda x: x)
        require_enterprise_admin_patcher.start()
        cls.addClassCleanup(require_enterprise_admin_patcher.stop)

        login_and_domain_required_patcher = patch.object(
            domain_decorators, 'login_and_domain_required', lambda x: x)
        login_and_domain_required_patcher.start()
        cls.addClassCleanup(login_and_domain_required_patcher.stop)


class EnterpriseDashboardEmailTests(TestCase):
    def test_custom_date_range_is_not_required(self):
        request = RequestFactory().get('/')
        request.couch_user = WebUser(username='test-user')
        request.account = billing_account(request.couch_user, request.couch_user)

        with patch.object(views, 'email_enterprise_report') as mocked:
            views.enterprise_dashboard_email(request, 'test-domain', EnterpriseReport.FORM_SUBMISSIONS)
            kwargs = mocked.delay.call_args[1]
            self.assertNotIn('start_date', kwargs)
            self.assertNotIn('end_date', kwargs)

    def test_custom_date_range_is_sent_to_celery(self):
        request = RequestFactory().get('/', data={
            'start_date': '2015-04-08T00:00:00.000000Z',
            'end_date': '2015-04-10T00:00:00.000000Z'
        })
        request.couch_user = WebUser(username='test-user')
        request.account = billing_account(request.couch_user, request.couch_user)

        with patch.object(views, 'email_enterprise_report') as mocked:
            views.enterprise_dashboard_email(request, 'test-domain', EnterpriseReport.FORM_SUBMISSIONS)
            kwargs = mocked.delay.call_args[1]
            self.assertEqual(kwargs['start_date'], datetime(year=2015, month=4, day=8))
            self.assertEqual(kwargs['end_date'], datetime(year=2015, month=4, day=10))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._patch_decorators()
        reload(views)

    @classmethod
    def _patch_decorators(cls):
        require_enterprise_admin_patcher = patch.object(
            enterprise_decorators, 'require_enterprise_admin', lambda x: x)
        require_enterprise_admin_patcher.start()
        cls.addClassCleanup(require_enterprise_admin_patcher.stop)

        login_and_domain_required_patcher = patch.object(
            domain_decorators, 'login_and_domain_required', lambda x: x)
        login_and_domain_required_patcher.start()
        cls.addClassCleanup(login_and_domain_required_patcher.stop)
