import time

import mock
from django.http import HttpResponse
from django.test import override_settings, SimpleTestCase, TestCase
from django.urls import path, include
from django.views import View
from testil import Regex

from corehq.apps.domain.models import Domain
from corehq.apps.reports.dispatcher import ReportDispatcher
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.users.models import WebUser
from corehq.util.timer import set_request_duration_reporting_threshold, TimingContext


@set_request_duration_reporting_threshold(0.1)
class SlowClassView(View):
    def get(self, request):
        time.sleep(0.2)
        return HttpResponse()


@set_request_duration_reporting_threshold(0.1)
def slow_function_view(request):
    timer = TimingContext()
    with timer("sleep"):
        time.sleep(0.2)
    response = HttpResponse()
    response.request_timer = timer
    return response


class TestReportDispatcher(ReportDispatcher):
    map_name = "REPORTS"
    prefix = "test"

    @classmethod
    def get_reports(cls, domain):
        return [('All Reports', [
            SlowReport,
            FastReport,
        ])]


class TestNoDomainReportDispatcher(ReportDispatcher):
    map_name = "REPORTS"
    prefix = "test_no_domain"

    @classmethod
    def get_reports(cls, domain):
        return [('All Reports', [
            NoDomainReport,
        ])]


class TestCustomReportDispatcher(TestNoDomainReportDispatcher):
    map_name = "REPORTS"
    prefix = "test_custom"

    def dispatch(self, request, *args, **kwargs):
        return CustomReport(request).view_response

    @classmethod
    def get_report_class_name(cls, domain, report_slug):
        raise Exception("Custom dispatcher's don't like this method")


class BaseReport(GenericReportView):
    name = "Test report"
    section_name = "test"

    @property
    def view_response(self):
        return HttpResponse(200)


@set_request_duration_reporting_threshold(0.1)
class SlowReport(BaseReport):
    dispatcher = TestReportDispatcher
    slug = 'slow_report'

    @property
    def view_response(self):
        time.sleep(0.2)
        return HttpResponse(200)


@set_request_duration_reporting_threshold(1)
class FastReport(BaseReport):
    dispatcher = TestReportDispatcher
    slug = 'fast_report'


class CustomReport(BaseReport):
    dispatcher = TestCustomReportDispatcher
    slug = 'custom_report'


class NoDomainReport(BaseReport):
    dispatcher = TestNoDomainReportDispatcher
    slug = 'admin_report'


urlpatterns = [
    path('slow_class', SlowClassView.as_view()),
    path('slow_function', slow_function_view),
    TestNoDomainReportDispatcher.url_pattern(),
    path('<domain>/', include([TestReportDispatcher.url_pattern()])),
    path('<domain>/custom/', include([TestCustomReportDispatcher.url_pattern()])),
]


@override_settings(
    ROOT_URLCONF='corehq.tests.test_middleware',
    MIDDLEWARE=('corehq.middleware.LogLongRequestMiddleware',)
)
@mock.patch('corehq.middleware.add_breadcrumb')
@mock.patch('corehq.middleware.notify_exception')
class TestLogLongRequestMiddleware(SimpleTestCase):

    def test_middleware_reports_slow_class_view(self, notify_exception, add_breadcrumb):
        res = self.client.get('/slow_class')
        self.assertEqual(res.status_code, 200)
        notify_exception.assert_called_once()
        add_breadcrumb.assert_not_called()

    def test_middleware_reports_slow_function_view_with_timer(self, notify_exception, add_breadcrumb):
        res = self.client.get('/slow_function')
        self.assertEqual(res.status_code, 200)
        notify_exception.assert_called_once()
        add_breadcrumb.assert_has_calls([
            mock.call(category="timing", message=Regex(r"^sleep: 0.\d+"), level="info")
        ])


@override_settings(
    ROOT_URLCONF='corehq.tests.test_middleware',
    DOMAIN_MODULE_MAP={"test_middleware": "corehq.tests.test_middleware"}
)
@mock.patch('corehq.middleware.notify_exception')
class TestLogLongRequestMiddlewareReports(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = Domain(name="long_request", is_active=True)
        cls.domain.save()

        cls.username = 'fingile'
        cls.password = '*******'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password, None, None)
        cls.user.set_role(cls.domain.name, 'admin')
        cls.user.save()

    def setUp(self):
        self.client.login(username=self.username, password=self.password)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super().tearDownClass()

    def test_slow_domain_report(self, notify_exception):
        res = self.client.get('/domain1/slow_report/')
        self.assertEqual(res.status_code, 200)
        notify_exception.assert_called_once()

    def test_fast_domain_report(self, notify_exception):
        res = self.client.get('/domain1/fast_report/')
        self.assertEqual(res.status_code, 200)
        notify_exception.assert_not_called()

    def test_no_domain_report(self, notify_exception):
        res = self.client.get('/admin_report/')
        self.assertEqual(res.status_code, 200)
        notify_exception.assert_not_called()

    def test_custom_report(self, notify_exception):
        res = self.client.get('/domain2/custom/custom_report/')
        self.assertEqual(res.status_code, 200)
        notify_exception.assert_not_called()
