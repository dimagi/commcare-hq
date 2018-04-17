from __future__ import absolute_import
from __future__ import unicode_literals
from mock.mock import MagicMock

from custom.yeksi_naa_reports.tests.utils import YeksiTestCase
from custom.yeksi_naa_reports.reports import Dashboard2Report


class TestDashboard2(YeksiTestCase):

    def test_loss_rate_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'month_start': '10',
            'year_start': '2017',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        loss_rate_report = dashboard2_report.report_context['reports'][0]['report_table']
        headers = loss_rate_report['headers'].as_export_table[0]
        rows = loss_rate_report['rows']
        total_row = loss_rate_report['total_row']
        self.assertEqual(
            headers,
            ['Region', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'New Test Region', u'43.41%', u'16.59%', u'7.56%', u'3.17%', u'1.95%', u'0.73%'],
                [u'Region Test', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Region 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Saint-Louis', u'6.36%', u'9.88%', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered'],
                [u'Dakar', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Fatick', u'no data entered', u'9.69%', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Thies', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Rate by Country', u'21.93%', u'11.79%', u'7.56%', u'3.17%', u'1.95%', u'0.73%']
        )

    def test_expiration_rate_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'month_start': '10',
            'year_start': '2017',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        expiration_rate_report = dashboard2_report.report_context['reports'][1]['report_table']
        headers = expiration_rate_report['headers'].as_export_table[0]
        rows = expiration_rate_report['rows']
        total_row = expiration_rate_report['total_row']
        self.assertEqual(
            headers,
            ['Region', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'New Test Region', u'38.77%', u'29.67%', u'17.14%', u'13.19%', u'7.76%', u'1.32%'],
                [u'Region Test', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Region 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Saint-Louis', u'6.50%', u'8.55%', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered'],
                [u'Dakar', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Fatick', u'no data entered', u'7.75%', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Thies', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Rate by Country', u'16.76%', u'12.79%', u'17.14%', u'13.19%', u'7.76%', u'1.32%']
        )

    def test_recovery_rate_by_district_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'month_start': '10',
            'year_start': '2017',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        recovery_rate_by_district_report = dashboard2_report.report_context['reports'][2]['report_table']
        headers = recovery_rate_by_district_report['headers'].as_export_table[0]
        rows = recovery_rate_by_district_report['rows']
        total_row = recovery_rate_by_district_report['total_row']
        self.assertEqual(
            headers,
            ['Region', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'District Sud', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'100.00%'],
                [u'District Khombole', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'100.00%'],
                [u'District Joal Fadiouth', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'100.00%'],
                [u'District Test 2', u'0.00%', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Thies', u'100.00%', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'District Mbao', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'100.00%'],
                [u'District Tivaoune', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'100.00%'],
                [u'District Pikine', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'100.00%'],
                [u'District Gu\xe9diawaye', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'100.00%'],
                [u'District M\xe9kh\xe9', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'100.00%'],
                [u'DISTRICT PNA', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'100.00%', u'100.00%'],
                [u'Dakar', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'0.00%'],
                [u'District Thiadiaye', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'100.00%'],
                [u'New York', u'19.15%', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Dakar', u'0.00%', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'District Centre', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'0.00%'],
                [u'District Test', u'100.00%', u'no data entered', u'no data entered', u'100.00%',
                 u'no data entered', u'no data entered']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Rate by Country', u'44.46%', u'0.00%', u'0.00%', u'100.00%', u'100.00%', u'75.86%']
        )

    def test_recovery_rate_by_pps_report_country_level(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'month_start': '10',
            'year_start': '2017',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        recovery_rate_by_pps_report = dashboard2_report.report_context['reports'][3]['report_table']
        headers = recovery_rate_by_pps_report['headers'].as_export_table[0]
        rows = recovery_rate_by_pps_report['rows']
        total_row = recovery_rate_by_pps_report['total_row']
        self.assertEqual(
            headers,
            ['Region', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'New Test Region', u'77.30%', u'63.63%', u'53.65%', u'55.93%', u'63.43%', u'90.75%'],
                [u'Region Test', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'28.12%', u'no data entered'],
                [u'Region 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'46.15%'],
                [u'Dakar', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'0.00%'],
                [u'Saint-Louis', u'68.82%', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Fatick', u'no data entered', u'90.47%', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Thies', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'100.00%']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Rate by Country', u'71.97%', u'69.87%', u'53.65%', u'55.93%', u'56.75%', u'89.46%']
        )

    def test_recovery_rate_by_pps_report_pps_level(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': 'ccf4430f5c3f493797486d6ce1c39682',
            'month_start': '10',
            'year_start': '2017',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        recovery_rate_by_pps_report = dashboard2_report.report_context['reports'][2]['report_table']
        headers = recovery_rate_by_pps_report['headers'].as_export_table[0]
        rows = recovery_rate_by_pps_report['rows']
        total_row = recovery_rate_by_pps_report['total_row']
        self.assertEqual(
            headers,
            ['PPS', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'P2', u'75.47%', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Rate by PPS', u'75.47%', u'0.00%', u'0.00%', u'0.00%', u'0.00%', u'0.00%']
        )

    def test_rupture_rate_by_pps_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'month_start': '10',
            'year_start': '2017',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        rupture_rate_by_pps_report = dashboard2_report.report_context['reports'][4]['report_table']
        headers = rupture_rate_by_pps_report['headers'].as_export_table[0]
        rows = rupture_rate_by_pps_report['rows']
        total_row = rupture_rate_by_pps_report['total_row']
        self.assertEqual(
            headers,
            ['PPS', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        expected = [
            [u'test pps 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'New Test PPS 1', u'35.00%', u'25.00%', u'20.00%', u'15.00%', u'5.00%', u'0.00%'],
            [u'PPS 3', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'F2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS Alexis', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'Virage 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'SL2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'G1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'Virage 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 3', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'7.69%', u'no data entered'],
            [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'F1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'Ngor', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'P2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'SL1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'P1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 3', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'Virage 2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'Pps test 2 bbb', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered', u'no data entered'],
            [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'Virage 2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'District Test 2', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered', u'no data entered'],
            [u'PPS 2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'New Test PPS 2', u'0.00%', u'0.00%', u'10.00%', u'20.00%', u'0.00%', u'0.00%'],
            [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered'],
            [u'PPS 2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
             u'no data entered', u'no data entered']
        ]
        self.assertEqual(
            len(rows),
            len(expected)
        )
        self.assertEqual(
            total_row,
            [u'Rate by Country', u'23.33%', u'16.67%', u'16.67%', u'16.67%', u'4.65%', u'0.00%']
        )
