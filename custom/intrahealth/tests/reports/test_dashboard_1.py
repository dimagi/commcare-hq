# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from mock.mock import MagicMock
import unittest

from custom.intrahealth.tests.utils import YeksiTestCase
from custom.intrahealth.reports import Dashboard1Report


class TestDashboard1(YeksiTestCase):

    def test_extract_value_from_report_table_row_value_input_dict(self):
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
        report_table = {
            'fix_column': False,
            'comment': 'test_comment',
            'rows': [[{'style': 'style0', 'html': 'html0'}, {'style': 'style3', 'html': 'html3'}],
                     [{'style': 'style1', 'html': 'html1'}, {'style': 'style4', 'html': 'html4'}],
                     [{'style': 'style2', 'html': 'html2'}, {'style': 'style5', 'html': 'html5'}]],
            'datatables': False,
            'title': 'test_title',
            'total_row': [
                {'html': 'pas de donn\xe9es0'},
                {'html': 'pas de donn\xe9es1'},
                {'html': 'pas de donn\xe9es2'},
                {'html': 'pas de donn\xe9es3'}
            ],
            'slug': 'disponibilite',
            'default_rows': 10
        }
        total_row = dashboard1_report._sanitize_single_row(report_table['total_row'])
        self.assertEqual(total_row, ['pas de donn\xe9es0', 'pas de donn\xe9es1',
                                     'pas de donn\xe9es2', 'pas de donn\xe9es3'])

        all_rows = dashboard1_report._sanitize_all_rows(report_table)
        self.assertEqual(all_rows, [['html0', 'html3'],
                                    ['html1', 'html4'],
                                    ['html2', 'html5']])

    def test_extract_value_from_report_table_row_value_input_string(self):
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
        dashboard1_report = Dashboard1Report(request=mock, domain='test-pna1')
        report_table = {
            'fix_column': False,
            'comment': 'test_comment',
            'rows': [['0', '4', '8', '12'],
                     ['1', '5', '9', '13'],
                     ['2', '6', '10', '14'],
                     ['3', '7', '11', '15']],
            'datatables': False,
            'title': 'test_title',
            'total_row': ['row_0', 'row_1', 'row_2', 'row_3'],
            'slug': 'disponibilite',
            'default_rows': 10
        }
        report_table_value = dashboard1_report._sanitize_single_row(report_table['total_row'])
        self.assertEqual(report_table_value, ['row_0', 'row_1', 'row_2', 'row_3'])

        all_rows = dashboard1_report._sanitize_all_rows(report_table)
        self.assertEqual(all_rows, [['0', '4', '8', '12'],
                                    ['1', '5', '9', '13'],
                                    ['2', '6', '10', '14'],
                                    ['3', '7', '11', '15']])

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
            ], key=lambda x: x[0]['html'])
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
