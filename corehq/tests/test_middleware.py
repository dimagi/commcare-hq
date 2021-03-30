import time

import mock
from django.http import HttpResponse
from django.test import override_settings, SimpleTestCase
from django.urls import path
from django.views import View
from testil import Regex

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


urlpatterns = [
    path('slow_class', SlowClassView.as_view()),
    path('slow_function', slow_function_view),
]


@override_settings(ROOT_URLCONF='corehq.tests.test_middleware')
class TestLogLongRequestMiddleware(SimpleTestCase):

    @override_settings(MIDDLEWARE=('corehq.middleware.LogLongRequestMiddleware',))
    @mock.patch('corehq.middleware.add_breadcrumb')
    @mock.patch('corehq.middleware.notify_exception')
    def test_middleware_reports_slow_class_view(self, notify_exception, add_breadcrumb):
        res = self.client.get('/slow_class')
        self.assertEqual(res.status_code, 200)
        notify_exception.assert_called_once()
        add_breadcrumb.assert_not_called()

    @override_settings(MIDDLEWARE=('corehq.middleware.LogLongRequestMiddleware',))
    @mock.patch('corehq.middleware.add_breadcrumb')
    @mock.patch('corehq.middleware.notify_exception')
    def test_middleware_reports_slow_function_view_with_timer(self, notify_exception, add_breadcrumb):
        res = self.client.get('/slow_function')
        self.assertEqual(res.status_code, 200)
        notify_exception.assert_called_once()
        add_breadcrumb.assert_has_calls([
            mock.call(category="timing", message=Regex(r"^sleep: 0.\d+"), level="info")
        ])
