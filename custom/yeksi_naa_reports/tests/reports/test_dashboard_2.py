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
                ['New Test Region', '43.41%', '16.59%', '7.56%', '3.17%', '1.95%', '0.73%'],
                ['Region Test', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données'],
                ['Region 1', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données'],
                ['Saint-Louis', '6.36%', '9.88%', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données'],
                ['Dakar', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données'],
                ['Fatick', 'pas de données', '9.69%', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données'],
                ['Thies', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Taux par Pays', '21.93%', '11.79%', '7.56%', '3.17%', '1.95%', '0.73%']
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
                [{'html': 'New Test Region'}, {'style': 'color: red', 'html': '38.77%'},
                 {'style': 'color: red', 'html': '29.67%'}, {'style': 'color: red', 'html': '17.14%'},
                 {'style': 'color: red', 'html': '13.19%'}, {'style': 'color: red', 'html': '7.76%'},
                 {'style': '', 'html': '1.32%'}],
                [{'html': 'Region Test'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}],
                [{'html': 'Region 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}],
                [{'html': 'Dakar'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}],
                [{'html': 'Saint-Louis'}, {'style': 'color: red', 'html': '6.50%'},
                 {'style': 'color: red', 'html': '8.55%'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}],
                [{'html': 'Fatick'}, {'html': 'pas de donn\xe9es'}, {'style': 'color: red', 'html': '7.75%'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}],
                [{'html': 'Thies'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                {'html': 'Taux par Pays'},
                {'style': 'color: red', 'html': '16.76%'},
                {'style': 'color: red', 'html': '12.79%'},
                {'style': 'color: red', 'html': '17.14%'},
                {'style': 'color: red', 'html': '13.19%'},
                {'style': 'color: red', 'html': '7.76%'},
                {'style': '', 'html': '1.32%'}
            ]
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
                ['District Sud', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', '100.00%'],
                ['District Khombole', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données', '100.00%'],
                ['District Joal Fadiouth', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données', '100.00%'],
                ['District Test 2', '0.00%', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données'],
                ['Thies', '100.00%', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données'],
                ['District Mbao', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', '100.00%'],
                ['District Tivaoune', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données', '100.00%'],
                ['District Pikine', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données', '100.00%'],
                ['District Gu\xe9diawaye', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données', '100.00%'],
                ['District M\xe9kh\xe9', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données', '100.00%'],
                ['DISTRICT PNA', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 '100.00%', '100.00%'],
                ['Dakar', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', '0.00%'],
                ['District Thiadiaye', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données', '100.00%'],
                ['New York', '19.15%', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données'],
                ['Dakar', '0.00%', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données'],
                ['District Centre', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données', '0.00%'],
                ['District Test', '100.00%', 'pas de données', 'pas de données', '100.00%',
                 'pas de données', 'pas de données']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Taux par Pays', '44.46%', '0.00%', '0.00%', '100.00%', '100.00%', '75.86%']
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
                ['New Test Region', '77.30%', '63.63%', '53.65%', '55.93%', '63.43%', '90.75%'],
                ['Region Test', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 '28.12%', 'pas de données'],
                ['Region 1', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', '46.15%'],
                ['Dakar', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', '0.00%'],
                ['Saint-Louis', '68.82%', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données'],
                ['Fatick', 'pas de données', '90.47%', 'pas de données', 'pas de données',
                 'pas de données', 'pas de données'],
                ['Thies', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données', '100.00%']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Taux par Pays', '71.97%', '69.87%', '53.65%', '55.93%', '56.75%', '89.46%']
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
                ['P2', '75.47%', 'pas de données', 'pas de données', 'pas de données', 'pas de données',
                 'pas de données']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Taux par PPS', '75.47%', '0.00%', '0.00%', '0.00%', '0.00%', '0.00%']
        )
