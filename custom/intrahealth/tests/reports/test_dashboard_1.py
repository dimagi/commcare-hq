# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from mock.mock import MagicMock
import unittest

from custom.intrahealth.tests.utils import YeksiTestCase
from custom.intrahealth.reports import Dashboard1Report


class TestDashboard1(YeksiTestCase):

    def test_availability_report(self):
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
            rows,
            sorted([
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
                    {'style': '', 'html': '100.00%'},
                    {'style': 'color: red', 'html': '0.00%'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': '100.00%'},
                    {'style': 'color: red', 'html': '58.33%'}
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
                    {'html': 'Saint-Louis'},
                    {'style': 'color: red', 'html': '75.00%'},
                    {'style': 'color: red', 'html': '33.33%'},
                    {'style': '', 'html': '100.00%'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': '100.00%'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': 'color: red', 'html': '77.08%'}
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
                {'style': 'color: red', 'html': '90.00%'},
                {'style': 'color: red', 'html': '33.33%'},
                {'style': '', 'html': '100.00%'},
                {'style': 'color: red', 'html': '80.00%'},
                {'style': '', 'html': '100.00%'},
                {'style': 'color: red', 'html': '88.24%'},
                {'style': 'color: red', 'html': '83.67%'}
            ]
        )

    @unittest.skip("This fails consistently on travis")
    def test_availability_report_with_chosen_program(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'program': 'a99fe8331e3dbcc127917e41af45ad81',
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
            rows,
            sorted([
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
                    {'html': 'Thies'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': '100.00%'},
                    {'style': '', 'html': '100.00%'}
                ]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                {'html': 'Disponibilit\xe9 (%)'},
                {'style': '', 'html': '100.00%'},
                {'html': 'pas de donn\xe9es'},
                {'style': '', 'html': '100.00%'},
                {'style': '', 'html': '100.00%'},
                {'style': '', 'html': '100.00%'},
                {'style': 'color: red', 'html': '66.67%'},
                {'style': 'color: red', 'html': '91.67%'}
            ]
        )

    def test_availability_report_pps_level(self):
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
            rows,
            sorted([
                [
                    {'html': 'P2'},
                    {'style': '', 'html': '100%'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': '100%'},
                    {'style': '', 'html': 'pas de donn\xe9es'},
                    {'style': '', 'html': '100.00%'}
                ]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                {'html': 'Disponibilit\xe9 (%)'},
                {'style': '', 'html': '100.00%'},
                {'html': 'pas de donn\xe9es'},
                {'html': 'pas de donn\xe9es'},
                {'html': 'pas de donn\xe9es'},
                {'style': '', 'html': '100.00%'},
                {'html': 'pas de donn\xe9es'},
                {'style': '', 'html': '100.00%'}
            ]
        )

    def test_rupture_rate_by_pps_report(self):
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

        dashboard1_report = Dashboard1Report(request=mock, domain='test-pna')

        rupture_rate_by_pps_report = dashboard1_report.report_context['reports'][1]['report_table']
        headers = rupture_rate_by_pps_report['headers'].as_export_table[0]
        rows = rupture_rate_by_pps_report['rows']
        total_row = rupture_rate_by_pps_report['total_row']
        self.assertEqual(
            headers,
            ['PPS', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018', 'Taux moyen']
        )
        expected = [
            [{'html': 'District Test 2'}, {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'F1'}, {'html': 'pas de donn\xe9es'}, {'style': 'color: red', 'html': '50.00%'},
             {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': 'color: red', 'html': '16.67%'}],
            [{'html': 'F2'}, {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'},
             {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'G1'}, {'html': 'pas de donn\xe9es'}, {'style': 'color: red', 'html': '66.67%'},
             {'html': 'pas de donn\xe9es'}, {'style': 'color: red', 'html': '33.33%'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': 'color: red', 'html': '50.00%'}],
            [{'html': 'Ngor'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'P1'}, {'style': 'color: red', 'html': '33.33%'},
             {'style': 'color: red', 'html': '50.00%'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': 'color: red', 'html': '37.50%'}],
            [{'html': 'P2'}, {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': 'color: red', 'html': '46.15%'}, {'html': 'pas de donn\xe9es'},
             {'style': 'color: red', 'html': '46.15%'}],
            [{'html': 'PPS 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}],
            [{'html': 'PPS 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}],
            [{'html': 'PPS 2'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 2'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 2'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 3'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 3'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'PPS 3'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': 'color: red', 'html': '50.00%'}, {'style': 'color: red', 'html': '50.00%'}],
            [{'html': 'PPS Alexis'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'Pps test 2 bbb'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'},
             {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}],
            [{'html': 'SL1'}, {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'SL2'}, {'style': '', 'html': '0.00%'}, {'style': 'color: red', 'html': '50.00%'},
             {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
             {'style': 'color: red', 'html': '12.50%'}],
            [{'html': 'Virage 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': 'color: red', 'html': '20.00%'}, {'style': 'color: red', 'html': '20.00%'}],
            [{'html': 'Virage 1'}, {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'Virage 2'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}],
            [{'html': 'Virage 2'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'style': '', 'html': '0.00%'}, {'style': '', 'html': '0.00%'}],
            [{'html': 'test pps 1'}, {'html': 'pas de donn\xe9es'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}, {'html': 'pas de donn\xe9es'},
             {'html': 'pas de donn\xe9es'}, {'style': '', 'html': '0.00%'}]
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
                {'html': 'Taux par Pays'}, {'style': 'color: red', 'html': '8.33%'},
                {'style': 'color: red', 'html': '35.71%'}, {'style': '', 'html': '0.00%'},
                {'style': 'color: red', 'html': '5.00%'}, {'style': 'color: red', 'html': '21.43%'},
                {'style': 'color: red', 'html': '4.17%'}, {'style': 'color: red', 'html': '11.35%'}
            ]
        )
