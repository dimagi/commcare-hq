from django.test import SimpleTestCase

from corehq.apps.userreports.reports.util import ReportExport
from corehq.apps.userreports.reports.view import ConfigurableReportView


class VeryFakeReportExport(ReportExport):
    def __init__(self, data):
        self._data = data

    def get_table(self):
        return self._data


class VeryFakeReportView(ConfigurableReportView):
    # note: this is very coupled to what it tests below, but it beats bootstrapping a whole UCR thing

    def __init__(self, data):
        self._data = data

    @property
    def report_export(self):
        return VeryFakeReportExport(self._data)


class ReportRenderingTest(SimpleTestCase):

    def test_email_response_unicode(self):
        report = VeryFakeReportView(data=[
            ['hello', 'हिन्दी']
        ])
        # this used to fail: https://manage.dimagi.com/default.asp?263803
        report.email_response
