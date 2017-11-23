from __future__ import absolute_import

from mock.mock import MagicMock

from custom.intrahealth.reports.fiche_consommation_report import FicheConsommationReport
from custom.intrahealth.tests.reports.util import ReportTestCase


class TestFicheConsommation(ReportTestCase):

    def test_report_data(self):
        mock = MagicMock()
        mock.couch_user = self.web_user
        mock.GET = {
            'location_id': 'd1',
            'startdate': '2017-11-01',
            'enddate': '2017-11-30'
        }

        fiche_report = FicheConsommationReport(request=mock, domain='test-domain')
        header = fiche_report.headers
        rows = fiche_report.rows

        self.assertEqual(
            [column_group.html for column_group in header],
            ['', 'Product 1', 'Product 2', 'Product 3']
        )
        self.assertEqual(
            rows,
            [
                [
                    u'PPS 1',
                    {'sort_key': 10, 'html': 10}, {'sort_key': 5, 'html': 5}, {'sort_key': 5, 'html': 5},
                    {'sort_key': 2, 'html': 2}, {'sort_key': 2, 'html': 2}, {'sort_key': 0, 'html': 0},
                    {'sort_key': 6, 'html': 6}, {'sort_key': 4, 'html': 4}, {'sort_key': 2, 'html': 2}
                ],
                [
                    u'PPS 2',
                    {'sort_key': 13, 'html': 13}, {'sort_key': 11, 'html': 11}, {'sort_key': 2, 'html': 2},
                    {'sort_key': 0, 'html': 0}, {'sort_key': 0, 'html': 0}, {'sort_key': 0, 'html': 0},
                    {'sort_key': 150, 'html': 150}, {'sort_key': 11, 'html': 11}, {'sort_key': 139, 'html': 139}
                ]
            ]
        )
