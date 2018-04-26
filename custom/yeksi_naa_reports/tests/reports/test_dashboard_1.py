# coding=utf-8
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
            ['Région', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018', 'Taux moyen de disponibilité']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [
                    {'html': 'New Test Region'},
                    {'style': 'color: red', 'html': '50.00%'},
                    {'style': 'color: red', 'html': '50.00%'},
                    {'style': 'color: red', 'html': '0.00%'},
                    {'style': 'color: red', 'html': '0.00%'},
                    {'style': 'color: red', 'html': '50.00%'},
                    {'style': '', 'html': '100.00%'},
                    {'style': 'color: red', 'html': '41.67%'}
                ],
                [
                    {'html': 'Region Test'},
                    {'style': '', 'html': '100.00%'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': '100.00%'},
                    {'style': '', 'html': '100.00%'},
                    {'style': '', 'html': '100.00%'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': '100.00%'}
                ],
                [
                    {'html': 'Region 1'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': 'color: red', 'html': '50.00%'},
                    {'style': 'color: red', 'html': '50.00%'}
                ],
                [
                    {'html': 'Saint-Louis'},
                    {'style': 'color: red', 'html': '75.00%'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': 'color: red', 'html': '75.00%'}
                ],
                [
                    {'html': 'Dakar'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': '100.00%'},
                    {'style': '', 'html': '100.00%'}
                ],
                [
                    {'html': 'Fatick'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': 'color: red', 'html': '33.33%'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': 'color: red', 'html': '33.33%'}
                ],
                [
                    {'html': 'Thies'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': 'color: red', 'html': '87.50%'},
                    {'style': 'color: red', 'html': '87.50%'}
                ]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                {'html': 'Disponibilit\xe9 (%)'},
                {'style': 'color: red', 'html': '83.33%'},
                {'style': 'color: red', 'html': '40.00%'},
                {'style': 'color: red', 'html': '33.33%'},
                {'style': 'color: red', 'html': '66.67%'},
                {'style': 'color: red', 'html': '83.33%'},
                {'style': 'color: red', 'html': '88.89%'},
                {'style': 'color: red', 'html': '76.00%'}
            ]
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
            ['PPS', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018', 'Taux moyen de disponibilité']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [
                    {'html': 'P2'},
                    {'style': '', 'html': '100%'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': '100.00%'}
                ]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                {'html': 'Disponibilit\xe9 (%)'},
                {'style': 'color: red', 'html': '0.00%'},
                {'style': 'color: red', 'html': '0.00%'},
                {'style': 'color: red', 'html': '0.00%'},
                {'style': 'color: red', 'html': '0.00%'},
                {'style': 'color: red', 'html': '0.00%'},
                {'style': 'color: red', 'html': '0.00%'},
                {'style': 'color: red', 'html': '0.00%'}
            ]
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

        dashboard1_report = Dashboard1Report(request=mock, domain='test-pna')

        rupture_rate_by_pps_report = dashboard1_report.report_context['reports'][1]['report_table']
        headers = rupture_rate_by_pps_report['headers'].as_export_table[0]
        rows = rupture_rate_by_pps_report['rows']
        total_row = rupture_rate_by_pps_report['total_row']
        self.assertEqual(
            headers,
            ['PPS', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018']
        )
        expected = [
            [{'html': 'test pps 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'New Test PPS 1'}, {'style': 'color: red', 'html': '35.00%'},
             {'style': 'color: red', 'html': '25.00%'}, {'style': 'color: red', 'html': '20.00%'},
             {'style': 'color: red', 'html': '15.00%'}, {'style': 'color: red', 'html': '5.00%'},
             {'style': '', 'html': '0.00%'}],
            [{'html': 'P2'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'F2'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS Alexis'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'Virage 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'G1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'Virage 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 3'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 2'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', {'style': 'color: red', 'html': '7.69%'}, 'pas de donn\xe9es'],
            [{'html': 'SL2'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'F1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 3'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'Ngor'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 3'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'SL1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'P1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'Virage 2'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'Pps test 2 bbb'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'Virage 2'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'District Test 2'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 2'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'New Test PPS 2'}, {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'},
             {'style': 'color: red', 'html': '10.00%'}, {'style': 'color: red', 'html': '20.00%'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 1'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
            [{'html': 'PPS 2'}, 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
             'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es']
        ]
        self.assertEqual(
            len(rows),
            len(expected)
        )
        for row in expected:
            self.assertIn(row, rows)
        self.assertEqual(
            total_row,
            [
                {'html': 'Taux par Pays'},
                {'style': 'color: red', 'html': '23.33%'},
                {'style': 'color: red', 'html': '16.67%'},
                {'style': 'color: red', 'html': '16.67%'},
                {'style': 'color: red', 'html': '16.67%'},
                {'style': 'color: red', 'html': '4.65%'},
                {'style': '', 'html': '0.00%'}
            ]
        )
