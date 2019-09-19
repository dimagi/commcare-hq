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
            [['LERANE COLY', 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0]]
        )

    def test_fiche_consommation_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        fiche_consommation_report2_report = FicheConsommationReport2(request=mock, domain='test-pna')

        fiche_consommation_report = fiche_consommation_report2_report.report_context['reports'][0]['report_table']
        headers = fiche_consommation_report['headers'].as_export_table[0]
        rows = fiche_consommation_report['rows']
        self.assertEqual(
            headers,
            ['', 'CU', ' ', ' ', 'Collier', ' ', ' ', 'DIU', ' ', ' ', 'Depo-Provera', ' ', ' ',
             'Jadelle', ' ', ' ', 'Microgynon/Lof.', ' ', ' ', 'Microlut/Ovrette', ' ', ' ',
             'Preservatif Feminin', ' ', ' ', 'Preservatif Masculin', ' ', ' ']
        )
        self.assertEqual(
            rows,
            [
                ['DEBI TIQUET', 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
                ['DIOGO', 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
                ['LERANE COLY', 1, 1, 0, 0, 0, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
                ['NDIAWAR RICHARD TOLL', 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 1, 1, 0,
                 1, 1, 0],
                ['NIANGUE DIAW', 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
                ['PS CAMP MILITAIRE', 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1,
                 1, 0],
                ['PS DIOKOUL WAGUE', 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1,
                 0],
                ['PS NGOR', 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
                ['PS PLLES ASS. UNITE 12', 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0,
                 1, 1, 0]
            ]
        )
