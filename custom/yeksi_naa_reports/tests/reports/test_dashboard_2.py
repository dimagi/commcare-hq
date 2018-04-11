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
            'month_start': '1',
            'year_start': '2018',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        loss_rate_report = dashboard2_report.report_context['reports'][0]['report_table']
        headers = loss_rate_report['headers'].as_export_table[0]
        rows = loss_rate_report['rows']
        self.assertEqual(
            headers,
            ['Region', 'January 2018', 'February 2018', 'March 2018', 'Target']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['Region 1', 'no data entered', 'no data entered', '1000.00%'],
                ['Dakar', 'no data entered', 'no data entered', '52200.00%'],
                ['Region Test', 'no data entered', '2000.00%', 'no data entered'],
                ['Thies', 'no data entered', 'no data entered', '2300.00%']
            ], key=lambda x: x[0])
        )

    def test_expiration_rate_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'month_start': '1',
            'year_start': '2018',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        expiration_rate_report = dashboard2_report.report_context['reports'][1]['report_table']
        headers = expiration_rate_report['headers'].as_export_table[0]
        rows = expiration_rate_report['rows']
        self.assertEqual(
            headers,
            ['Region', 'January 2018', 'February 2018', 'March 2018', 'Target']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['Region 1', 'no data entered', 'no data entered', '0.00%'],
                ['Dakar', 'no data entered', 'no data entered', '0.00%'],
                ['Region Test', 'no data entered', '0.00%', 'no data entered'],
                ['Thies', 'no data entered', 'no data entered', '0.00%']
            ], key=lambda x: x[0])
        )

    def test_recovery_rate_by_pps_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': 'f400d0ba6bdb456bb2d5f9843eb766fe',
            'month_start': '1',
            'year_start': '2018',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        recovery_rate_by_pps_report = dashboard2_report.report_context['reports'][2]['report_table']
        headers = recovery_rate_by_pps_report['headers'].as_export_table[0]
        rows = recovery_rate_by_pps_report['rows']
        self.assertEqual(
            headers,
            ['PPS', 'January 2018', 'February 2018', 'March 2018', 'Target']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['test pps 1', '0.00%', 'no data entered', 'no data entered']
            ], key=lambda x: x[0])
        )

    def test_recovery_rate_by_district_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'month_start': '1',
            'year_start': '2018',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        recovery_rate_by_district_report = dashboard2_report.report_context['reports'][2]['report_table']
        headers = recovery_rate_by_district_report['headers'].as_export_table[0]
        rows = recovery_rate_by_district_report['rows']
        self.assertEqual(
            headers,
            ['Region', 'January 2018', 'February 2018', 'March 2018', 'Target']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['District Sud', 'no data entered', 'no data entered', '100.00%'],
                ['District Khombole', 'no data entered', 'no data entered', '100.00%'],
                ['District Joal Fadiouth', 'no data entered', 'no data entered', '100.00%'],
                ['Dakar', 'no data entered', 'no data entered', '0.00%'],
                ['District Tivaoune', 'no data entered', 'no data entered', '100.00%'],
                ['District Pikine', 'no data entered', 'no data entered', '100.00%'],
                ['District Gu\xe9diawaye', 'no data entered', 'no data entered', '100.00%'],
                ['District M\xe9kh\xe9', 'no data entered', 'no data entered', '100.00%'],
                ['DISTRICT PNA', 'no data entered', '100.00%', '100.00%'],
                ['District Thiadiaye', 'no data entered', 'no data entered', '100.00%'],
                ['District Mbao', 'no data entered', 'no data entered', '100.00%'],
                ['District Centre', 'no data entered', 'no data entered', '0.00%'],
                ['District Test', '100.00%', 'no data entered', 'no data entered']
            ], key=lambda x: x[0])
        )

    def test_rupture_rate_by_pps_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'month_start': '1',
            'year_start': '2018',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard2_report = Dashboard2Report(request=mock, domain='test-pna')

        rupture_rate_by_pps_report = dashboard2_report.report_context['reports'][3]['report_table']
        headers = rupture_rate_by_pps_report['headers'].as_export_table[0]
        rows = rupture_rate_by_pps_report['rows']
        self.assertEqual(
            headers,
            ['PPS', 'January 2018', 'February 2018', 'March 2018', 'Target']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['test pps 1', '0.00%', 'no data entered', 'no data entered'],
                ['PPS 1', 'no data entered', 'no data entered', '0.00%'],
                ['PPS 3', 'no data entered', 'no data entered', '0.00%'],
                ['PPS 1', 'no data entered', 'no data entered', '0.00%'],
                ['Pps test 2 bbb', '0.00%', '0.00%', 'no data entered'],
                ['PPS Alexis', '0.00%', 'no data entered', 'no data entered'],
                ['PPS 2', 'no data entered', 'no data entered', '0.00%'],
                ['Virage 1', '0.00%', 'no data entered', 'no data entered'],
                ['PPS 3', 'no data entered', '0.00%', 'no data entered'],
                ['Virage 1', 'no data entered', 'no data entered', '100.00%'],
                ['PPS 2', 'no data entered', '0.00%', 'no data entered'],
                ['PPS 1', 'no data entered', '46.15%', 'no data entered'],
                ['PPS 3', 'no data entered', 'no data entered', '100.00%'],
                ['PPS 1', 'no data entered', 'no data entered', '0.00%'],
                ['PPS 1', 'no data entered', 'no data entered', '0.00%'],
                ['PPS 1', 'no data entered', 'no data entered', '0.00%'],
                ['PPS 1', 'no data entered', 'no data entered', '0.00%'],
                ['PPS 1', 'no data entered', 'no data entered', '0.00%'],
                ['Virage 2', 'no data entered', 'no data entered', '0.00%'],
                ['PPS 1', 'no data entered', 'no data entered', '0.00%'],
                ['PPS 2', 'no data entered', 'no data entered', '0.00%'],
                ['PPS 1', 'no data entered', 'no data entered', '0.00%'],
                ['PPS 1', 'no data entered', 'no data entered', '0.00%']
            ], key=lambda x: x[0])
        )
