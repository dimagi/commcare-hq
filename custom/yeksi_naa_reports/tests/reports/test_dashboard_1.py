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
            'month_start': '10',
            'year_start': '2017',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard1_report = Dashboard1Report(request=mock, domain='test-pna')

        availability_report = dashboard1_report.report_context['reports'][0]['report_table']
        headers = availability_report['headers'].as_export_table[0]
        rows = availability_report['rows']
        total_row = availability_report['total_row']

        self.assertEqual(
            headers,
            ['Region', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018', 'Avg. Availability']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['New Test Region', '50.00%', '50.00%', '0.00%', '0.00%', '50.00%', '100.00%', '41.67%'],
                ['Region Test', '100.00%', 'no data entered', '100.00%', '100.00%', '100.00%',
                 'no data entered', '100.00%'],
                ['Region 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '50.00%', '50.00%'],
                ['Saint-Louis', '75.00%', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '75.00%'],
                ['Dakar', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '100.00%', '100.00%'],
                ['Fatick', 'no data entered', '33.33%', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '33.33%'],
                ['Thies', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '87.50%', '87.50%']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Availability (%)', '83.33%', '40.00%', '33.33%', '66.67%', '83.33%', '88.89%', '76.00%']
        )

    def test_availability_report_pps_level(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': 'ccf4430f5c3f493797486d6ce1c39682',
            'month_start': '10',
            'year_start': '2017',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard1_report = Dashboard1Report(request=mock, domain='test-pna')

        availability_report = dashboard1_report.report_context['reports'][0]['report_table']
        headers = availability_report['headers'].as_export_table[0]
        rows = availability_report['rows']
        total_row = availability_report['total_row']

        self.assertEqual(
            headers,
            ['PPS', 'October 2017', 'November 2017', 'December 2017', 'January 2018', 'February 2018',
             'March 2018', 'Avg. Availability']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['P2', '100%', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '100.00%']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Availability (%)', '100.00%', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered', '100.00%']
        )
