# coding=utf-8
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
            ['Région', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'New Test Region', u'43.41%', u'16.59%', u'7.56%', u'3.17%', u'1.95%', u'0.73%'],
                [u'Region Test', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Region 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Saint-Louis', u'6.36%', u'9.88%', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données'],
                [u'Dakar', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Fatick', u'pas de données', u'9.69%', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Thies', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Taux par Pays', u'21.93%', u'11.79%', u'7.56%', u'3.17%', u'1.95%', u'0.73%']
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
            ['Région', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'New Test Region', u'38.77%', u'29.67%', u'17.14%', u'13.19%', u'7.76%', u'1.32%'],
                [u'Region Test', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Region 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Saint-Louis', u'6.50%', u'8.55%', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données'],
                [u'Dakar', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Fatick', u'pas de données', u'7.75%', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Thies', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Taux par Pays', u'16.76%', u'12.79%', u'17.14%', u'13.19%', u'7.76%', u'1.32%']
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
            ['Région', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'District Sud', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'100.00%'],
                [u'District Khombole', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données', u'100.00%'],
                [u'District Joal Fadiouth', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données', u'100.00%'],
                [u'District Test 2', u'0.00%', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Thies', u'100.00%', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'District Mbao', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'100.00%'],
                [u'District Tivaoune', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données', u'100.00%'],
                [u'District Pikine', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données', u'100.00%'],
                [u'District Gu\xe9diawaye', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données', u'100.00%'],
                [u'District M\xe9kh\xe9', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données', u'100.00%'],
                [u'DISTRICT PNA', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'100.00%', u'100.00%'],
                [u'Dakar', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'0.00%'],
                [u'District Thiadiaye', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données', u'100.00%'],
                [u'New York', u'19.15%', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Dakar', u'0.00%', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'District Centre', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données', u'0.00%'],
                [u'District Test', u'100.00%', u'pas de données', u'pas de données', u'100.00%',
                 u'pas de données', u'pas de données']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Taux par Pays', u'44.46%', u'0.00%', u'0.00%', u'100.00%', u'100.00%', u'75.86%']
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
            ['Région', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'New Test Region', u'77.30%', u'63.63%', u'53.65%', u'55.93%', u'63.43%', u'90.75%'],
                [u'Region Test', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'28.12%', u'pas de données'],
                [u'Region 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'46.15%'],
                [u'Dakar', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'0.00%'],
                [u'Saint-Louis', u'68.82%', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Fatick', u'pas de données', u'90.47%', u'pas de données', u'pas de données',
                 u'pas de données', u'pas de données'],
                [u'Thies', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données', u'100.00%']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Taux par Pays', u'71.97%', u'69.87%', u'53.65%', u'55.93%', u'56.75%', u'89.46%']
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
            ['PPS', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'P2', u'75.47%', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
                 u'pas de données']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Taux par PPS', u'75.47%', u'0.00%', u'0.00%', u'0.00%', u'0.00%', u'0.00%']
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
            ['PPS', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018']
        )
        expected = [
            [u'test pps 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'New Test PPS 1', u'35.00%', u'25.00%', u'20.00%', u'15.00%', u'5.00%', u'0.00%'],
            [u'PPS 3', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'F2', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS Alexis', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'Virage 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'SL2', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'G1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'Virage 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 3', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 2', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'7.69%', u'pas de données'],
            [u'PPS 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'F1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'Ngor', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'P2', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'SL1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'P1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 3', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'Virage 2', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'Pps test 2 bbb', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données', u'pas de données'],
            [u'PPS 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'Virage 2', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'District Test 2', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données', u'pas de données'],
            [u'PPS 2', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'New Test PPS 2', u'0.00%', u'0.00%', u'10.00%', u'20.00%', u'0.00%', u'0.00%'],
            [u'PPS 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 1', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données'],
            [u'PPS 2', u'pas de données', u'pas de données', u'pas de données', u'pas de données',
             u'pas de données', u'pas de données']
        ]
        self.assertEqual(
            len(rows),
            len(expected)
        )
        for row in expected:
            self.assertIn(row, rows)
        self.assertEqual(
            total_row,
            [u'Taux par Pays', u'23.33%', u'16.67%', u'16.67%', u'16.67%', u'4.65%', u'0.00%']
        )
