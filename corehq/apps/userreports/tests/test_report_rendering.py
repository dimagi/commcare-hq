# coding: utf-8
from __future__ import absolute_import
from django.test import SimpleTestCase
from corehq.apps.userreports.reports.view import ConfigurableReport


class VeryFakeReportView(ConfigurableReport):
    # note: this is very coupled to what it tests below, but it beats bootstrapping a whole UCR thing

    def __init__(self, data):
        self._data = data

    @property
    def export_table(self):
        return self._data


class ReportRenderingTest(SimpleTestCase):

    def test_email_response_unicode(self):
        report = VeryFakeReportView(data=[
            ['hello', u'हिन्दी']
        ])
        # this used to fail: https://manage.dimagi.com/default.asp?263803
        report.email_response
