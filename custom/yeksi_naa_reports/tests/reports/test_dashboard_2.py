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
            [u'R\xe9gion', u'Octobre 2017', u'Novembre 2017', u'D\xe9cembre 2017', u'Janvier 2018',
             u'F\xe9vrier 2018', u'Mars 2018', u'Taux moyen']
        )
        self.assertEqual(
            rows,
            sorted([
                [{u'html': u'New Test Region'}, {u'html': u'43.41%'}, {u'html': u'16.59%'}, {u'html': u'7.56%'},
                 {u'html': u'3.17%'}, {u'html': u'1.95%'}, {u'html': u'0.73%'}, {u'html': u'12.24%'}],
                [{u'html': u'Region Test'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}],
                [{u'html': u'Region 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}],
                [{u'html': u'Saint-Louis'}, {u'html': u'6.36%'}, {u'html': u'9.88%'},
                 {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'8.00%'}],
                [{u'html': u'Dakar'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}],
                [{u'html': u'Fatick'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'9.69%'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'9.69%'}],
                [{u'html': u'Thies'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [{u'html': u'Taux par Pays'}, {u'html': u'21.93%'}, {u'html': u'11.79%'}, {u'html': u'7.56%'},
             {u'html': u'3.17%'}, {u'html': u'1.95%'}, {u'html': u'0.73%'}, {u'html': u'10.81%'}]
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
            [u'R\xe9gion', u'Octobre 2017', u'Novembre 2017', u'D\xe9cembre 2017', u'Janvier 2018',
             u'F\xe9vrier 2018', u'Mars 2018', u'Taux moyen']
        )
        self.assertEqual(
            rows,
            sorted([
                [{u'html': u'New Test Region'}, {u'style': u'color: red', u'html': u'38.77%'},
                 {u'style': u'color: red', u'html': u'29.67%'}, {u'style': u'color: red', u'html': u'17.14%'},
                 {u'style': u'color: red', u'html': u'13.19%'}, {u'style': u'color: red', u'html': u'7.76%'},
                 {u'style': u'', u'html': u'1.32%'}, {u'style': u'color: red', u'html': u'17.97%'}],
                [{u'html': u'Region Test'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}],
                [{u'html': u'Region 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}],
                [{u'html': u'Saint-Louis'}, {u'style': u'color: red', u'html': u'6.50%'},
                 {u'style': u'color: red', u'html': u'8.55%'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'style': u'color: red', u'html': u'7.47%'}],
                [{u'html': u'Dakar'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}],
                [{u'html': u'Fatick'}, {u'html': u'pas de donn\xe9es'},
                 {u'style': u'color: red', u'html': u'7.75%'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'style': u'color: red', u'html': u'7.75%'}],
                [{u'html': u'Thies'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                {u'html': u'Taux par Pays'},
                {u'style': u'color: red', u'html': u'16.76%'},
                {u'style': u'color: red', u'html': u'12.79%'},
                {u'style': u'color: red', u'html': u'17.14%'},
                {u'style': u'color: red', u'html': u'13.19%'},
                {u'style': u'color: red', u'html': u'7.76%'},
                {u'style': u'', u'html': u'1.32%'},
                {u'style': u'color: red', u'html': u'12.85%'}
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
            [u'R\xe9gion', u'Octobre 2017', u'Novembre 2017', u'D\xe9cembre 2017', u'Janvier 2018',
             u'F\xe9vrier 2018', u'Mars 2018', u'Taux moyen']
        )
        self.assertEqual(
            rows,
            sorted([
                [{u'html': u'District Sud'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'100.00%'}, {u'html': u'100.00%'}],
                [{u'html': u'District Khombole'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'100.00%'}, {u'html': u'100.00%'}],
                [{u'html': u'District Joal Fadiouth'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'100.00%'}, {u'html': u'100.00%'}],
                [{u'html': u'District Test 2'}, {u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'0.00%'}],
                [{u'html': u'Thies'}, {u'html': u'100.00%'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'100.00%'}],
                [{u'html': u'District Mbao'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'100.00%'}, {u'html': u'100.00%'}],
                [{u'html': u'District Tivaoune'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'100.00%'}, {u'html': u'100.00%'}],
                [{u'html': u'District Pikine'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'100.00%'}, {u'html': u'100.00%'}],
                [{u'html': u'District Gu\xe9diawaye'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'100.00%'}, {u'html': u'100.00%'}],
                [{u'html': u'District M\xe9kh\xe9'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'100.00%'}, {u'html': u'100.00%'}],
                [{u'html': u'DISTRICT PNA'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'100.00%'},
                 {u'html': u'100.00%'}, {u'html': u'100.00%'}],
                [{u'html': u'Dakar'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'0.00%'}, {u'html': u'0.00%'}],
                [{u'html': u'District Thiadiaye'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'100.00%'}, {u'html': u'100.00%'}],
                [{u'html': u'New York'}, {u'html': u'19.15%'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'19.15%'}],
                [{u'html': u'Dakar'}, {u'html': u'0.00%'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'0.00%'}],
                [{u'html': u'District Centre'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'0.00%'}, {u'html': u'0.00%'}],
                [{u'html': u'District Test'}, {u'html': u'100.00%'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'100.00%'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'100.00%'}]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [{u'html': u'Taux par Pays'}, {u'html': u'44.46%'}, {u'html': u'0.00%'}, {u'html': u'0.00%'},
             {u'html': u'100.00%'}, {u'html': u'100.00%'}, {u'html': u'75.86%'}, {u'html': u'80.43%'}]
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
             'Février 2018', 'Mars 2018', u'Taux moyen']
        )
        self.assertEqual(
            rows,
            sorted([
                [{u'html': u'New Test Region'}, {u'html': u'77.30%'}, {u'html': u'63.63%'}, {u'html': u'53.65%'},
                 {u'html': u'55.93%'}, {u'html': u'63.43%'}, {u'html': u'90.75%'}, {u'html': u'67.39%'}],
                [{u'html': u'Region Test'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'28.12%'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'28.12%'}],
                [{u'html': u'Region 1'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'46.15%'}, {u'html': u'46.15%'}],
                [{u'html': u'Dakar'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'0.00%'}, {u'html': u'0.00%'}],
                [{u'html': u'Saint-Louis'}, {u'html': u'68.82%'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'68.82%'}],
                [{u'html': u'Fatick'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'90.47%'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'90.47%'}],
                [{u'html': u'Thies'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'}, {u'html': u'pas de donn\xe9es'},
                 {u'html': u'100.00%'}, {u'html': u'100.00%'}]], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [{u'html': u'Taux par Pays'}, {u'html': u'71.97%'}, {u'html': u'69.87%'}, {u'html': u'53.65%'},
             {u'html': u'55.93%'}, {u'html': u'56.75%'}, {u'html': u'89.46%'}, {u'html': u'67.01%'}]
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
            [u'PPS', u'Octobre 2017', u'Novembre 2017', u'D\xe9cembre 2017', u'Janvier 2018', u'F\xe9vrier 2018',
             u'Mars 2018', u'Taux moyen']
        )
        self.assertEqual(
            rows,
            sorted([
                [
                    {u'html': u'P2'},
                    {u'html': u'75.47%'},
                    {u'html': u'pas de donn\xe9es'},
                    {u'html': u'pas de donn\xe9es'},
                    {u'html': u'pas de donn\xe9es'},
                    {u'html': u'pas de donn\xe9es'},
                    {u'html': u'pas de donn\xe9es'},
                    {u'html': u'75.47%'}
                ]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [{u'html': u'Taux par PPS'}, {u'html': u'75.47%'}, {u'html': u'0.00%'}, {u'html': u'0.00%'},
             {u'html': u'0.00%'}, {u'html': u'0.00%'}, {u'html': u'0.00%'}, {u'html': u'75.47%'}]
        )
