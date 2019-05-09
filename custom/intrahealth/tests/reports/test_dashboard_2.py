# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from mock.mock import MagicMock

from custom.intrahealth.tests.utils import YeksiTestCase
from custom.intrahealth.reports import Dashboard2Report


class TestDashboard2(YeksiTestCase):

    def test_loss_rate_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'program': '',
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
            ['R\xe9gion', 'Octobre 2017', 'Novembre 2017', 'D\xe9cembre 2017', 'Janvier 2018',
             'F\xe9vrier 2018', 'Mars 2018', 'Taux moyen']
        )
        self.assertEqual(
            rows,
            sorted([
                [{'html': 'Dakar'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}],
                [{'html': 'Fatick'}, {'html': 'pas de donn\xe9es'}, {'html': '9.69%'}, {'html': '5.49%'},
                 {'html': '0.75%'}, {'html': 'pas de donn\xe9es'}, {'html': '0.00%'}, {'html': '5.48%'}],
                [{'html': 'Region 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}],
                [{'html': 'Region Test'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}],
                [{'html': 'Saint-Louis'}, {'html': '6.36%'}, {'html': '9.88%'}, {'html': '0.00%'},
                 {'html': 'pas de donn\xe9es'}, {'html': '2.94%'}, {'html': 'pas de donn\xe9es'},
                 {'html': '5.92%'}],
                [{'html': 'Thies'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}]
            ], key=lambda x: x[0]['html'])
        )
        self.assertEqual(
            total_row,
            [
                {'html': 'Taux par Pays'}, {'html': '6.36%'}, {'html': '9.79%'}, {'html': '3.61%'},
                {'html': '0.75%'}, {'html': '2.94%'}, {'html': '0.00%'}, {'html': '5.74%'}
            ]
        )

    def test_expiration_rate_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'program': '',
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
            ['R\xe9gion', 'Octobre 2017', 'Novembre 2017', 'D\xe9cembre 2017', 'Janvier 2018',
             'F\xe9vrier 2018', 'Mars 2018', 'Taux moyen']
        )
        self.assertEqual(
            rows,
            sorted([
                [{'html': 'Dakar'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}],
                [{'html': 'Fatick'}, {'html': 'pas de donn\xe9es'},
                 {'style': 'color: red', 'html': '7.75%'}, {'style': '', 'html': '3.59%'},
                 {'style': '', 'html': '3.51%'}, {'html': 'pas de donn\xe9es'},
                 {'style': '', 'html': '2.70%'}, {'style': 'color: red', 'html': '5.11%'}],
                [{'html': 'Region 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}],
                [{'html': 'Region Test'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}],
                [{'html': 'Saint-Louis'}, {'style': 'color: red', 'html': '6.50%'},
                 {'style': 'color: red', 'html': '8.55%'}, {'style': '', 'html': '0.00%'},
                 {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '1.12%'},
                 {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '4.93%'}],
                [{'html': 'Thies'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}]
            ], key=lambda x: x[0]['html'])
        )
        self.assertEqual(
            total_row,
            [
                {'html': 'Taux par Pays'}, {'style': 'color: red', 'html': '6.50%'},
                {'style': 'color: red', 'html': '8.17%'}, {'style': '', 'html': '2.34%'},
                {'style': '', 'html': '3.51%'}, {'style': '', 'html': '1.12%'},
                {'style': '', 'html': '2.70%'}, {'style': '', 'html': '5.00%'}
            ]
        )

    def test_recovery_rate_by_district_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'program': '',
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
            ['R\xe9gion', 'Octobre 2017', 'Novembre 2017', 'D\xe9cembre 2017', 'Janvier 2018',
             'F\xe9vrier 2018', 'Mars 2018', 'Taux moyen']
        )
        self.assertListEqual(
            rows[0:1],
            [
                [{'html': 'DISTRICT PNA'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': '100.00%'},
                 {'html': '100.00%'}, {'html': '100.00%'}],
            ]
        )
        # Current implementation does not guarantee order of rows with the same district name
        self.assertCountEqual(
            rows[1:3],
            [
                [{'html': 'Dakar'}, {'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': '0.00%'}],
                [{'html': 'Dakar'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '0.00%'}, {'html': '0.00%'}],
            ]
        )
        self.assertListEqual(
            rows[3:],
            [
                [{'html': 'District Centre'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '0.00%'}, {'html': '0.00%'}],
                [{'html': 'District Gu\xe9diawaye'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '100.00%'}, {'html': '100.00%'}],
                [{'html': 'District Joal Fadiouth'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '100.00%'}, {'html': '100.00%'}],
                [{'html': 'District Khombole'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '100.00%'}, {'html': '100.00%'}],
                [{'html': 'District Mbao'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '100.00%'}, {'html': '100.00%'}],
                [{'html': 'District M\xe9kh\xe9'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '100.00%'}, {'html': '100.00%'}],
                [{'html': 'District Pikine'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '100.00%'}, {'html': '100.00%'}],
                [{'html': 'District Sud'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '100.00%'}, {'html': '100.00%'}],
                [{'html': 'District Test'}, {'html': '100.00%'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': '100.00%'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': '100.00%'}],
                [{'html': 'District Test 2'}, {'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': '0.00%'}],
                [{'html': 'District Thiadiaye'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '100.00%'}, {'html': '100.00%'}],
                [{'html': 'District Tivaoune'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '100.00%'}, {'html': '100.00%'}],
                [{'html': 'New York'}, {'html': '19.15%'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': '19.15%'}],
                [{'html': 'Thies'}, {'html': '100.00%'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': '100.00%'}],
            ]
        )
        self.assertEqual(
            total_row,
            [{'html': 'Taux par Pays'}, {'html': '44.46%'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': '100.00%'}, {'html': '100.00%'}, {'html': '75.86%'},
             {'html': '80.43%'}]
        )

    def test_recovery_rate_by_pps_report_country_level(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'program': '',
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
             'Février 2018', 'Mars 2018', 'Taux moyen']
        )
        self.assertEqual(
            rows,
            sorted([
                [{'html': 'Dakar'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '0.00%'}, {'html': '0.00%'}],
                [{'html': 'Fatick'}, {'html': 'pas de donn\xe9es'}, {'html': '90.47%'}, {'html': '2.75%'},
                 {'html': '0.00%'}, {'html': 'pas de donn\xe9es'}, {'html': '0.00%'}, {'html': '29.88%'}],
                [{'html': 'Region 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '92.31%'}, {'html': '92.31%'}],
                [{'html': 'Region Test'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': '64.98%'},
                 {'html': 'pas de donn\xe9es'}, {'html': '64.98%'}],
                [{'html': 'Saint-Louis'}, {'html': '78.36%'}, {'html': '87.68%'}, {'html': '0.00%'},
                 {'html': 'pas de donn\xe9es'}, {'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
                 {'html': '65.73%'}],
                [{'html': 'Thies'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
                 {'html': '100.00%'}, {'html': '100.00%'}]
            ], key=lambda x: x[0]['html'])
        )
        self.assertEqual(
            total_row,
            [
                {'html': 'Taux par Pays'}, {'html': '78.36%'}, {'html': '88.53%'}, {'html': '1.59%'},
                {'html': '0.00%'}, {'html': '15.90%'}, {'html': '22.13%'}, {'html': '54.80%'}
            ]
        )

    def test_recovery_rate_by_pps_report_pps_level(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': 'ccf4430f5c3f493797486d6ce1c39682',
            'program': '',
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
            ['PPS', 'Octobre 2017', 'Novembre 2017', 'D\xe9cembre 2017', 'Janvier 2018', 'F\xe9vrier 2018',
             'Mars 2018', 'Taux moyen']
        )
        self.assertEqual(
            rows,
            sorted([
                [{'html': 'P2'}, {'html': '93.02%'}, {'html': 'pas de donn\xe9es'},
                 {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': '0.00%'},
                 {'html': 'pas de donn\xe9es'}, {'html': '42.55%'}]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                {'html': 'Taux par PPS'}, {'html': '93.02%'}, {'html': 'pas de donn\xe9es'},
                {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': '0.00%'},
                {'html': 'pas de donn\xe9es'}, {'html': '42.55%'}
            ]
        )
