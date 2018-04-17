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
                ['New Test Region', '43.41%', '16.59%', '7.56%', '3.17%', '1.95%', '0.73%'],
                ['Region Test', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Region 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Saint-Louis', '6.36%', '9.88%', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered'],
                ['Dakar', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Fatick', 'no data entered', '9.69%', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Thies', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Rate by Country', '21.93%', '11.79%', '7.56%', '3.17%', '1.95%', '0.73%']
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
                ['New Test Region', '38.77%', '29.67%', '17.14%', '13.19%', '7.76%', '1.32%'],
                ['Region Test', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Region 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Saint-Louis', '6.50%', '8.55%', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered'],
                ['Dakar', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Fatick', 'no data entered', '7.75%', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Thies', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Rate by Country', '16.76%', '12.79%', '17.14%', '13.19%', '7.76%', '1.32%']
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
                ['District Sud', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '100.00%'],
                ['District Khombole', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '100.00%'],
                ['District Joal Fadiouth', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '100.00%'],
                ['District Test 2', '0.00%', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Thies', '100.00%', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['District Mbao', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '100.00%'],
                ['District Tivaoune', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '100.00%'],
                ['District Pikine', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '100.00%'],
                ['District Gu\xe9diawaye', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '100.00%'],
                ['District M\xe9kh\xe9', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '100.00%'],
                ['DISTRICT PNA', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 '100.00%', '100.00%'],
                ['Dakar', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '0.00%'],
                ['District Thiadiaye', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '100.00%'],
                ['New York', '19.15%', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Dakar', '0.00%', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['District Centre', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '0.00%'],
                ['District Test', '100.00%', 'no data entered', 'no data entered', '100.00%',
                 'no data entered', 'no data entered']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Rate by Country', '44.46%', '0.00%', '0.00%', '100.00%', '100.00%', '75.86%']
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
                ['New Test Region', '77.30%', '63.63%', '53.65%', '55.93%', '63.43%', '90.75%'],
                ['Region Test', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 '28.12%', 'no data entered'],
                ['Region 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '46.15%'],
                ['Dakar', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '0.00%'],
                ['Saint-Louis', '68.82%', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Fatick', 'no data entered', '90.47%', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['Thies', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '100.00%']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Rate by Country', '71.97%', '69.87%', '53.65%', '55.93%', '56.75%', '89.46%']
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
                ['P2', '75.47%', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Rate by PPS', '75.47%', '0.00%', '0.00%', '0.00%', '0.00%', '0.00%']
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
            ['test pps 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['New Test PPS 1', '35.00%', '25.00%', '20.00%', '15.00%', '5.00%', '0.00%'],
            ['PPS 3', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['F2', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS Alexis', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['Virage 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['SL2', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['G1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['Virage 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 3', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 2', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             '7.69%', 'no data entered'],
            ['PPS 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['F1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['Ngor', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['P2', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['SL1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['P1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 3', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['Virage 2', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['Pps test 2 bbb', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered', 'no data entered'],
            ['PPS 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['Virage 2', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['District Test 2', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered', 'no data entered'],
            ['PPS 2', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['New Test PPS 2', '0.00%', '0.00%', '10.00%', '20.00%', '0.00%', '0.00%'],
            ['PPS 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered'],
            ['PPS 2', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
             'no data entered', 'no data entered']
        ]
        self.assertEqual(
            len(rows),
            len(expected)
        )
        self.assertEqual(
            total_row,
            ['Rate by Country', '23.33%', '16.67%', '16.67%', '16.67%', '4.65%', '0.00%']
        )
