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
                [u'New Test Region', u'50.00%', u'50.00%', u'0.00%', u'0.00%', u'50.00%', u'100.00%', u'41.67%'],
                [u'Region Test', u'100.00%', u'no data entered', u'100.00%', u'100.00%', u'100.00%',
                 u'no data entered', u'100.00%'],
                [u'Region 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'50.00%', u'50.00%'],
                [u'Saint-Louis', u'75.00%', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'75.00%'],
                [u'Dakar', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'100.00%', u'100.00%'],
                [u'Fatick', u'no data entered', u'33.33%', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'33.33%'],
                [u'Thies', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'87.50%', u'87.50%']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Availability (%)', u'83.33%', u'40.00%', u'33.33%', u'66.67%', u'83.33%', u'88.89%', u'76.00%']
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
            [u'PPS', u'October 2017', u'November 2017', u'December 2017', u'January 2018', u'February 2018',
             u'March 2018', u'Avg. Availability']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'P2', u'100%', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'100.00%']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Availability (%)', u'100.00%', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered', u'100.00%']
        )
