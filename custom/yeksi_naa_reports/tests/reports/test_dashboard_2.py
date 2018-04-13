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
        self.assertEqual(
            headers,
            ['Region', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
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
        self.assertEqual(
            headers,
            ['Region', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
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

    def test_recovery_rate_by_pps_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': 'f400d0ba6bdb456bb2d5f9843eb766fe',
            'month_start': '10',
            'year_start': '2017',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        recovery_rate_by_pps_report = dashboard2_report.report_context['reports'][2]['report_table']
        headers = recovery_rate_by_pps_report['headers'].as_export_table[0]
        rows = recovery_rate_by_pps_report['rows']
        self.assertEqual(
            headers,
            ['PPS', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'test pps 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered']
            ], key=lambda x: x[0])
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

        rupture_rate_by_pps_report = dashboard2_report.report_context['reports'][3]['report_table']
        headers = rupture_rate_by_pps_report['headers'].as_export_table[0]
        rows = rupture_rate_by_pps_report['rows']
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
                [u'P2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'F2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'PPS Alexis', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'PPS 2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
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
                 u'46.15%', u'no data entered'],
                [u'SL2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'F1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Ngor', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'PPS 3', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
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
                [u'Pps test 2 bbb', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Virage 2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'PPS 2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'District Test 2', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'no data entered'],
                [u'PPS 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'Virage 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered']
            ]
        self.assertEqual(
            len(rows),
            len(expected)
        )
        for row in expected:
            self.assertIn(
                row,
                rows
            )
