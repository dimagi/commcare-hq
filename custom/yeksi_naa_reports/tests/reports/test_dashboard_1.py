from __future__ import absolute_import
from __future__ import unicode_literals
from mock.mock import MagicMock

from custom.yeksi_naa_reports.tests.utils import YeksiTestCase
from custom.yeksi_naa_reports.reports import Dashboard1Report


class TestDashboard1(YeksiTestCase):

    def test_availability_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'month_start': '1',
            'year_start': '2018',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard1_report = Dashboard1Report(request=mock, domain='test-pna')

        availability_report = dashboard1_report.report_context['reports'][0]['report_table']
        headers = availability_report['headers'].as_export_table[0]
        rows = availability_report['rows']

        self.assertEqual(
            headers,
            ['Region', 'January 2018', 'February 2018', 'March 2018', 'Avg. Availability']
        )
        self.assertEqual(
            rows,
            [
                [u'Region 1', u'50.00%', u'50.00%', u'50.00%', u'50.00%'],
                [u'Dakar', u'100.00%', u'100.00%', u'100.00%', u'100.00%'],
                [u'Region Test', u'100.00%', u'100.00%', u'100.00%', u'100.00%'],
                [u'Thies', u'87.50%', u'87.50%', u'87.50%', u'87.50%']
            ]
        )
