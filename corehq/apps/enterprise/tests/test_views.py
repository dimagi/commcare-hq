from django.test import SimpleTestCase, RequestFactory
from importlib import reload
from unittest.mock import patch

from corehq.apps.enterprise import views

from corehq.apps.enterprise import decorators as enterprise_decorators
from corehq.apps.domain import decorators as domain_decorators

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
