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
                ['Region 1', 'no data entered', 'no data entered', '50.00%', '16.67%'],
                ['Dakar', 'no data entered', 'no data entered', '0.00%', '0.00%'],
                ['Region Test', '0.00%', '0.00%', 'no data entered', '0.00%'],
                ['Thies', 'no data entered', 'no data entered', '12.50%', '4.17%']
            ]
        )
