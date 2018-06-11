# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import datetime

from mock.mock import MagicMock

from custom.intrahealth.tests.utils import YeksiTestCase
from custom.intrahealth.reports import FicheConsommationReport2
from dimagi.utils.dates import DateSpan


class TestFicheConsommationReport2(YeksiTestCase):

    def test_fiche_consommation_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '1991b4dfe166335e342f28134b85fcac',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        fiche_consommation_report2_report = FicheConsommationReport2(request=mock, domain='test-pna')

        fiche_consommation_report = fiche_consommation_report2_report.report_context['reports'][0]['report_table']
        headers = fiche_consommation_report['headers'].as_export_table[0]
        rows = fiche_consommation_report['rows']
        self.assertEqual(
            headers,
            ['', 'CU', ' ', ' ', 'DIU', ' ', ' ', 'Depo-Provera', ' ', ' ',
             'Jadelle', ' ', ' ', 'Microgynon/Lof.', ' ', ' ', 'Microlut/Ovrette', ' ', ' ',
             'Preservatif Feminin', ' ', ' ', 'Preservatif Masculin', ' ', ' ']
        )
        self.assertEqual(
            rows,
            [
                ['LERANE COLY', 0, 0, 0, 0, 0, 0, 8, 8, 0, 0, 0, 0, 0, 0, 0, 3, 3, 0, 0, 0, 0, 0, 0, 0]
            ]
        )
