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
            ['', 'CU', u' ', ' ', 'Collier', ' ', ' ', 'DIU', u' ', ' ', 'Depo-Provera', ' ', ' ',
             'Jadelle', ' ', ' ', 'Microgynon/Lof.', ' ', ' ', 'Microlut/Ovrette', ' ', ' ',
             'Preservatif Feminin', ' ', ' ', 'Preservatif Masculin', ' ', ' ', 'Sayana Press', ' ', ' ']
        )
        self.assertEqual(
            rows,
            [
                ['BICOLE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 11, 11, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0,
                 2, 2, 0, 0, 0, 0],
                ['C.S FOUNDIOUGNE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 67, 67, 0, 4, 0, 4, 103, 103, 0, 25, 0,
                 25, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['C.S SOKONE', 0, 0, 0, 0, 0, 0, 1, 0, 1, 109, 109, 0, 18, 18, 0, 78, 0, 78, 9, 0,
                 9, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['COULAR SOCE', 0, 0, 0, 0, 0, 0, 2, 0, 2, 22, 22, 0, 2, 2, 0, 5, 5, 0, 0, 0, 0, 0,
                 0, 0, 10, 10, 0, 0, 0, 0],
                ['CS DIOFFIOR', 0, 0, 0, 0, 0, 0, 0, 0, 0, 87, 87, 0, 4, 0, 4, 120, 120, 0, 15, 15,
                 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['DAROU MARNANE GOSSAS', 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                 0, 0, 0, 16, 0, 16, 0, 0, 0],
                ['DIABEL', 0, 0, 0, 0, 0, 0, 0, 0, 0, 6, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0],
                ['DIAMNIANDIO FOUNDIOUGNE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 34, 20, 14, 4, 4, 0, 102, 102, 0,
                 8, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['DIONWAR', 0, 0, 0, 0, 0, 0, 0, 0, 0, 24, 24, 0, 3, 0, 3, 21, 21, 0, 0, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0, 0],
                ['FAOYE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 11, 11, 0, 6, 6, 0, 0, 0,
                 0, 0, 0, 0, 0, 0, 0],
                ['KARANG', 0, 0, 0, 0, 0, 0, 4, 4, 0, 91, 91, 0, 1, 1, 0, 45, 45, 0, 6, 6, 0, 0,
                 0, 0, 0, 0, 0, 0, 0, 0],
                ['LERANE COLY', 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 8, 0, 0, 0, 0, 0, 0, 0, 3, 3, 0, 0, 0,
                 0, 0, 0, 0, 0, 0, 0],
                ['MAR-LOTHIE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 34, 20, 14, 0, 0, 0, 8, 8, 0, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0, 0, 0],
                ['MBAR', 1, 1, 0, 0, 0, 0, 0, 0, 0, 79, 79, 0, 1, 0, 1, 45, 45, 0, 9, 9, 0, 0,
                 0, 0, 0, 0, 0, 0, 0, 0],
                ['MBAWENE SOULEY', 0, 0, 0, 0, 0, 0, 0, 0, 0, 16, 16, 0, 2, 2, 0, 6, 0, 6, 0, 0, 0,
                 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['MISSIRAH', 0, 0, 0, 0, 0, 0, 0, 0, 0, 11, 11, 0, 0, 0, 0, 9, 9, 0, 0, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0, 0],
                ['NEMA - NDING', 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10, 0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0,
                 0, 0, 16, 16, 0, 0, 0, 0],
                ['NEMABAH', 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0],
                ['NGAHOKHEME', 0, 0, 0, 0, 0, 0, 0, 0, 0, 39, 39, 0, 2, 0, 2, 30, 30, 0, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0, 0, 0],
                ['NGOTE MBADATTE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 13, 0, 0, 0, 0, 15, 15, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['NIODIOR', 0, 0, 0, 0, 0, 0, 0, 0, 0, 40, 40, 0, 0, 0, 0, 27, 27, 0, 9, 0, 9, 0, 0,
                 0, 0, 0, 0, 0, 0, 0],
                ['NIORO ALASSANE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 40, 40, 0, 8, 8, 0, 50, 50, 0, 0, 0, 0,
                 0, 0, 0, 8, 8, 0, 0, 0, 0],
                ['NOBANDANE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 19, 0, 0, 0, 0, 16, 16, 0, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0, 0, 0],
                ['OUADIOUR', 0, 0, 0, 0, 0, 0, 0, 0, 0, 18, 18, 0, 0, 0, 0, 35, 35, 0, 13, 13, 0,
                 0, 0, 0, 4, 4, 0, 0, 0, 0],
                ['PATAR SINE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 34, 34, 0, 3, 0, 3, 83, 83, 0, 0, 0, 0,
                 0, 0, 0, 12, 12, 0, 0, 0, 0],
                ['RAYON PRIVE DIOFFIOR', 5, 5, 0, 0, 0, 0, 0, 0, 0, 75, 75, 0, 6, 6, 0, 45, 45, 0,
                 6, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['SENGHOR', 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 10, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0,
                 0, 0, 0, 0, 0, 0, 0],
                ['SOBEME', 0, 0, 0, 0, 0, 0, 0, 0, 0, 21, 21, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0,
                 0, 0, 0, 0, 0, 0, 0],
                ['SOUM', 0, 0, 0, 0, 0, 0, 0, 0, 0, 43, 43, 0, 4, 4, 0, 45, 42, 3, 3, 0, 3, 0, 0,
                 0, 0, 0, 0, 0, 0, 0],
                ['SOUNDIANE DIMLE', 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 0, 13, 0, 0, 0, 18, 17, 1, 3, 0,
                 3, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            ]
        )
