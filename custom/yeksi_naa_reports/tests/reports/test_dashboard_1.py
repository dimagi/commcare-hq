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
            'program': '%%',
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
                    {u'html': u'Dakar'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'100.00%'}
                ],
                [
                    {u'html': u'Fatick'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'color: red', u'html': u'33.33%'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'color: red', u'html': u'0.00%'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'color: red', u'html': u'58.33%'}
                ],
                [
                    {u'html': u'Region 1'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'color: red', u'html': u'50.00%'},
                    {u'style': u'color: red', u'html': u'50.00%'}
                ],
                [
                    {u'html': u'Region Test'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'100.00%'}
                ],
                [
                    {u'html': u'Saint-Louis'},
                    {u'style': u'color: red', u'html': u'75.00%'},
                    {u'style': u'color: red', u'html': u'33.33%'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'color: red', u'html': u'77.08%'}
                ],
                [
                    {u'html': u'Thies'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'color: red', u'html': u'87.50%'},
                    {u'style': u'color: red', u'html': u'87.50%'}
                ]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                {u'html': u'Disponibilit\xe9 (%)'},
                {u'style': u'color: red', u'html': u'90.00%'},
                {u'style': u'color: red', u'html': u'33.33%'},
                {u'style': u'', u'html': u'100.00%'},
                {u'style': u'color: red', u'html': u'80.00%'},
                {u'style': u'', u'html': u'100.00%'},
                {u'style': u'color: red', u'html': u'88.24%'},
                {u'style': u'color: red', u'html': u'83.67%'}
            ]
        )

    def test_availability_report_with_chosen_program(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'program': '%a99fe8331e3dbcc127917e41af45ad81%',
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
                    {u'html': u'Region 1'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'color: red', u'html': u'50.00%'},
                    {u'style': u'color: red', u'html': u'50.00%'}
                ],
                [
                    {u'html': u'Region Test'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'100.00%'}
                ],
                [
                    {u'html': u'Thies'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'100.00%'},
                    {u'style': u'', u'html': u'100.00%'}
                ]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                {u'html': u'Disponibilit\xe9 (%)'},
                {u'style': u'', u'html': u'100.00%'},
                {u'html': u'pas de donn\xe9es'},
                {u'style': u'', u'html': u'100.00%'},
                {u'style': u'', u'html': u'100.00%'},
                {u'style': u'', u'html': u'100.00%'},
                {u'style': u'color: red', u'html': u'66.67%'},
                {u'style': u'color: red', u'html': u'91.67%'}
            ]
        )

    def test_availability_report_pps_level(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': 'ccf4430f5c3f493797486d6ce1c39682',
            'program': '%%',
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
                    {u'html': u'P2'},
                    {u'style': u'', u'html': u'100%'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'100%'},
                    {u'style': u'', u'html': u'pas de donn\xe9es'},
                    {u'style': u'', u'html': u'100.00%'}
                ]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                {u'html': u'Disponibilit\xe9 (%)'},
                {u'style': u'color: red', u'html': u'0.00%'},
                {u'style': u'color: red', u'html': u'0.00%'},
                {u'style': u'color: red', u'html': u'0.00%'},
                {u'style': u'color: red', u'html': u'0.00%'},
                {u'style': u'color: red', u'html': u'0.00%'},
                {u'style': u'color: red', u'html': u'0.00%'},
                {u'style': u'color: red', u'html': u'0.00%'}
            ]
        )

    def test_rupture_rate_by_pps_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'program': '%%',
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
            [{u'html': u'District Test 2'}, {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'F1'}, {u'html': u'pas de donn\xe9es'}, {u'style': u'color: red', u'html': u'50.00%'},
             {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'color: red', u'html': u'16.67%'}],
            [{u'html': u'F2'}, {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'},
             {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'G1'}, {u'html': u'pas de donn\xe9es'}, {u'style': u'color: red', u'html': u'66.67%'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'color: red', u'html': u'33.33%'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'color: red', u'html': u'50.00%'}],
            [{u'html': u'Ngor'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'P1'}, {u'style': u'color: red', u'html': u'33.33%'},
             {u'style': u'color: red', u'html': u'50.00%'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'color: red', u'html': u'40.00%'}],
            [{u'html': u'P2'}, {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'color: red', u'html': u'30.00%'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'color: red', u'html': u'30.00%'}],
            [{u'html': u'PPS 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}],
            [{u'html': u'PPS 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}],
            [{u'html': u'PPS 2'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 2'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 2'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 3'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 3'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'PPS 3'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'color: red', u'html': u'50.00%'}, {u'style': u'color: red', u'html': u'50.00%'}],
            [{u'html': u'PPS Alexis'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'Pps test 2 bbb'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'},
             {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'SL1'}, {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'SL2'}, {u'style': u'', u'html': u'0.00%'}, {u'style': u'color: red', u'html': u'50.00%'},
             {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'color: red', u'html': u'12.50%'}],
            [{u'html': u'Virage 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'color: red', u'html': u'20.00%'}, {u'style': u'color: red', u'html': u'20.00%'}],
            [{u'html': u'Virage 1'}, {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'Virage 2'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}],
            [{u'html': u'Virage 2'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'style': u'', u'html': u'0.00%'}, {u'style': u'', u'html': u'0.00%'}],
            [{u'html': u'test pps 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'},
             {u'html': u'pas de donn\xe9es'}, {u'style': u'', u'html': u'0.00%'}]
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
                {u'html': u'Taux par Pays'}, {u'style': u'color: red', u'html': u'7.14%'},
                {u'style': u'color: red', u'html': u'35.71%'}, {u'style': u'', u'html': u'0.00%'},
                {u'style': u'color: red', u'html': u'9.09%'}, {u'style': u'color: red', u'html': u'13.64%'},
                {u'style': u'color: red', u'html': u'4.65%'}, {u'style': u'color: red', u'html': u'10.81%'}
            ]
        )
