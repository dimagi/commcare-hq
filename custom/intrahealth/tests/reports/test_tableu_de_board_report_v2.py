# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import datetime

from mock.mock import MagicMock

from custom.intrahealth.tests.utils import YeksiTestCase
from custom.intrahealth.reports import TableuDeBoardReport2
from dimagi.utils.dates import DateSpan


class TestTableuDeBoardReportV2(YeksiTestCase):

    def test_conventure_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '1991b4dfe166335e342f28134b85fcac',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        conventure_report = tableu_de_board_report2_report.report_context['reports'][0]['report_table']
        headers = conventure_report['headers'].as_export_table[0]
        rows = conventure_report['rows']
        total_row = conventure_report['total_row']

        self.assertEqual(
            headers,
            [
                'Mois', 'No de PPS (number of PPS registered in that region)',
                'No de PPS planifie (number of PPS planned)',
                'No de PPS avec livrasion cet mois (number of PPS visited this month)',
                'Taux de couverture (coverage ratio)',
                'No de PPS avec donnees soumises (number of PPS which submitted data)',
                'Exhaustivite des donnees']
        )
        self.assertEqual(
            rows,
            [['Juillet', 0, 0, 1, '100.00%', 1, '100.00%']]
        )
        self.assertEqual(
            total_row,
            ['', 0, 0, 1, '100.00%', 1, '100.00%']
        )

    def test_conventure_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        conventure_report = tableu_de_board_report2_report.report_context['reports'][0]['report_table']
        headers = conventure_report['headers'].as_export_table[0]
        rows = conventure_report['rows']
        total_row = conventure_report['total_row']

        self.assertEqual(
            headers,
            [
                'Mois', 'No de PPS (number of PPS registered in that region)',
                'No de PPS planifie (number of PPS planned)',
                'No de PPS avec livrasion cet mois (number of PPS visited this month)',
                'Taux de couverture (coverage ratio)',
                'No de PPS avec donnees soumises (number of PPS which submitted data)',
                'Exhaustivite des donnees']
        )
        self.assertEqual(
            rows,
            [
                ['Juin', 0, 0, 9, '900.00%', 9, '100.00%'],
                ['Juillet', 0, 0, 6, '600.00%', 6, '100.00%']
            ]
        )
        self.assertEqual(
            total_row,
            ['', 0, 0, 15, '1500.00%', 15, '100.00%']
        )

    def test_PPS_avec_donnees_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '1991b4dfe166335e342f28134b85fcac',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        PPS_avec_donnees_report = tableu_de_board_report2_report.report_context['reports'][1]['report_table']
        headers = PPS_avec_donnees_report['headers'].as_export_table[0]
        rows = PPS_avec_donnees_report['rows']
        total_row = PPS_avec_donnees_report['total_row']
        self.assertEqual(
            headers,
            ['PPS', 'PPS Avec Donn\xe9es Soumises']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([['PASSY', 1]], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Total', 1]
        )

    def test_PPS_avec_donnees_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        PPS_avec_donnees_report = tableu_de_board_report2_report.report_context['reports'][1]['report_table']
        headers = PPS_avec_donnees_report['headers'].as_export_table[0]
        rows = PPS_avec_donnees_report['rows']
        total_row = PPS_avec_donnees_report['total_row']
        self.assertEqual(
            headers,
            ['PPS', 'PPS Avec Donn\xe9es Soumises']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['PS NGOR', 1], ['NIANGUE DIAW', 1], ['NDIAWAR RICHARD TOLL', 1], ['PS DIOKOUL WAGUE', 1],
                ['PS PLLES ASS. UNITE 12', 1], ['PS CAMP MILITAIRE', 1], ['DEBI TIQUET', 1], ['LERANE COLY', 1],
                ['DIOGO', 1]
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Total', 9]
        )

    def test_disp_des_products_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '1991b4dfe166335e342f28134b85fcac',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        disp_des_products_report = tableu_de_board_report2_report.report_context['reports'][2]['report_table']
        headers = disp_des_products_report['headers'].as_export_table[0]
        rows = disp_des_products_report['rows']
        self.assertEqual(
            headers,
            ['Quantity', 'CU', 'Collier', 'DIU', 'Depo-Provera', 'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [['Commandes', 0, 0, 0, 10800, 200, 0, 0, 0, 0],
             ['Raux', 0, 0, 0, 10800, 200, 0, 0, 0, 0],
             ['Taux', '0%', '0%', '0%', '100%', '100%', '0%', '0%', '0%', '0%']]
        )

    def test_disp_des_products_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        disp_des_products_report = tableu_de_board_report2_report.report_context['reports'][2]['report_table']
        headers = disp_des_products_report['headers'].as_export_table[0]
        rows = disp_des_products_report['rows']
        self.assertEqual(
            headers,
            ['Quantity', 'CU', 'Collier', 'DIU', 'Depo-Provera', 'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [['Commandes', 1842, 217, 2194, 90675, 7510, 113080, 7200, 4000, 48000],
             ['Raux', 1842, 217, 2194, 51308, 5810, 59080, 7200, 4000, 48000],
             ['Taux', '100%', '100%', '100%', '176%', '129%', '191%', '100%', '100%', '100%']]
        )

    def test_taux_de_ruptures_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '1991b4dfe166335e342f28134b85fcac',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        taux_de_ruptures_report = tableu_de_board_report2_report.report_context['reports'][3]['report_table']
        headers = taux_de_ruptures_report['headers'].as_export_table[0]
        rows = taux_de_ruptures_report['rows']
        total_row = taux_de_ruptures_report['total_row']

        self.assertEqual(
            headers,
            ['District', 'CU', u'Collier', 'DIU', u'Depo-Provera', 'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [['PASSY', 1, 0, 1, 1, 1, 1, 1, 1, 1], ['Total', 1, 0, 1, 1, 1, 1, 1, 1, 1]],
        )
        self.assertEqual(
            total_row,
            ['Taux rupture', '(1/1) 100.00%', '(0/1) 0.00%', '(1/1) 100.00%', '(1/1) 100.00%',
             '(1/1) 100.00%', '(1/1) 100.00%', '(1/1) 100.00%', '(1/1) 100.00%', '(1/1) 100.00%']
        )

    def test_taux_de_ruptures_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        taux_de_ruptures_report = tableu_de_board_report2_report.report_context['reports'][3]['report_table']
        headers = taux_de_ruptures_report['headers'].as_export_table[0]
        rows = taux_de_ruptures_report['rows']
        total_row = taux_de_ruptures_report['total_row']

        self.assertEqual(
            headers,
            ['PPS', 'CU', u'Collier', 'DIU', u'Depo-Provera', 'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [
                ['PS NGOR', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['GUELOR WOLOF', 1, 1, 1, 1, 1, 1, 1, 1, 1],
                ['NIANGUE DIAW', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['NDIAWAR RICHARD TOLL', 1, 1, 1, 1, 1, 1, 1, 1, 1],
                ['PS DE KOBILO', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['PS DIOKOUL WAGUE', 1, 1, 1, 1, 1, 1, 1, 1, 1],
                ['PS PLLES ASS. UNITE 12', 1, 1, 1, 1, 1, 1, 1, 1, 1],
                ['MBANE DAGANA', 0, 0, 0, 0, 0, 1, 1, 0, 0], ['PS CAMP MILITAIRE', 1, 1, 1, 1, 1, 1, 1, 1, 1],
                ['PS DE DOUMGA OURO ALPHA', 1, 1, 1, 1, 1, 1, 1, 1, 1],
                ['DEBI TIQUET', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['LERANE COLY', 1, 0, 1, 1, 1, 1, 1, 1, 1],
                ['GRAND THIES', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['DIENDER', 1, 1, 1, 1, 1, 1, 1, 1, 1],
                ['DIOGO', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['Total', 14, 13, 14, 14, 14, 15, 15, 14, 14]
            ],
        )
        self.assertEqual(
            total_row,
            ['Taux rupture', '(14/15) 93.33%', '(13/15) 86.67%', '(14/15) 93.33%', '(14/15) 93.33%',
             '(14/15) 93.33%', '(15/15) 100.00%', '(15/15) 100.00%', '(14/15) 93.33%', '(14/15) 93.33%']
        )

    def test_consommation_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '1991b4dfe166335e342f28134b85fcac',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        consommation_report = tableu_de_board_report2_report.report_context['reports'][4]['report_table']
        headers = consommation_report['headers'].as_export_table[0]
        rows = consommation_report['rows']
        total_row = consommation_report['total_row']

        self.assertEqual(
            headers,
            ['District', 'CU', u'Collier', 'DIU', u'Depo-Provera', 'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [['PASSY', 0, 0, 0, 8, 0, 0, 3, 0, 0]],
        )
        self.assertEqual(
            total_row,
            ['Total', 0, 0, 0, 8, 0, 0, 3, 0, 0]
        )

    def test_consommation_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        consommation_report = tableu_de_board_report2_report.report_context['reports'][4]['report_table']
        headers = consommation_report['headers'].as_export_table[0]
        rows = consommation_report['rows']
        total_row = consommation_report['total_row']

        self.assertEqual(
            headers,
            ['PPS', 'CU', u'Collier', 'DIU', u'Depo-Provera', 'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [
                ['PS NGOR', 0, 0, 0, 100, 6, 179, 13, 0, 6],
                ['GUELOR WOLOF', 0, 0, 0, 10, 0, 3, 0, 0, 0],
                ['NIANGUE DIAW', 0, 1, 0, 69, 2, 48, 9, 5, 32],
                ['NDIAWAR RICHARD TOLL', 0, 0, 0, 58, 0, 116, 3, 0, 0],
                ['PS DE KOBILO', 0, 0, 0, 9, 0, 19, 9, 0, 22],
                ['PS DIOKOUL WAGUE', 0, 0, 0, 28, 0, 33, 21, 0, 0],
                ['PS PLLES ASS. UNITE 12', 0, 0, 13, 139, 16, 215, 29, 10, 0],
                ['MBANE DAGANA', 0, 0, 0, 0, 0, 94, 3, 0, 0],
                ['PS CAMP MILITAIRE', 0, 0, 0, 4, 0, 100, 3, 0, 234],
                ['PS DE DOUMGA OURO ALPHA', 1, 0, 0, 5, 0, 30, 12, 0, 0],
                ['DEBI TIQUET', 0, 1, 1, 24, 4, 11, 17, 0, 66],
                ['LERANE COLY', 0, 0, 0, 8, 0, 0, 3, 0, 0],
                ['GRAND THIES', 5, 0, 5, 117, 5, 173, 57, 0, 70],
                ['DIENDER', 0, 0, 1, 46, 1, 64, 8, 0, 21],
                ['DIOGO', 0, 0, 3, 182, 3, 89, 15, 0, 10]
            ],
        )
        self.assertEqual(
            total_row,
            ['Total', 6, 2, 23, 799, 37, 1174, 202, 15, 461]
        )

    def test_taux_consommation_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '1991b4dfe166335e342f28134b85fcac',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        taux_consommation_report = tableu_de_board_report2_report.report_context['reports'][5]['report_table']
        headers = taux_consommation_report['headers'].as_export_table[0]
        rows = taux_consommation_report['rows']
        total_row = taux_consommation_report['total_row']

        self.assertEqual(
            headers,
            ['', 'CU', u' ', ' ', 'Collier', ' ', ' ', 'DIU', u' ', ' ', 'Depo-Provera', ' ', ' ',
             'Jadelle', ' ', ' ', 'Microgynon/Lof.', ' ', ' ', 'Microlut/Ovrette', ' ', ' ',
             'Preservatif Feminin', ' ', ' ', 'Preservatif Masculin', ' ', ' ']
        )
        self.assertEqual(
            rows,
            [
                ['DEBI TIQUET', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['DIENDER', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['DIOGO', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['GRAND THIES', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['GUELOR WOLOF', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['LERANE COLY', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['MBANE DAGANA', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['NDIAWAR RICHARD TOLL', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0},
                 '0.00%', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['NIANGUE DIAW', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['PASSY', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 3.0, 'html': 3.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 2.0, 'html': 2.0}, '0.00%',
                 {'sort_key': 8.0, 'html': 8.0}, {'sort_key': 52.0, 'html': 52.0}, '15.38%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 6.0, 'html': 6.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 42.0, 'html': 42.0}, '0.00%',
                 {'sort_key': 3.0, 'html': 3.0}, {'sort_key': 12.0, 'html': 12.0}, '25.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 100.0, 'html': 100.0}, '0.00%'],
                ['PS CAMP MILITAIRE', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0},
                 '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['PS DE DOUMGA OURO ALPHA', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0},
                 '0.00%', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['PS DE KOBILO', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['PS DIOKOUL WAGUE', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['PS NGOR', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['PS PLLES ASS. UNITE 12', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0},
                 '0.00%', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%']],
        )
        self.assertEqual(
            total_row,
            ['', 0.0, 3.0, '0.00%', 0, 0, '0.00%', 0.0, 2.0, '0.00%', 8.0, 52.0, '15.38%', 0.0, 6.0,
             '0.00%', 0.0, 42.0, '0.00%', 3.0, 12.0, '25.00%', 0.0, 5.0, '0.00%', 0.0, 100.0,
             '0.00%']
        )

    def test_taux_consommation_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        taux_consommation_report = tableu_de_board_report2_report.report_context['reports'][5]['report_table']
        headers = taux_consommation_report['headers'].as_export_table[0]
        rows = taux_consommation_report['rows']
        total_row = taux_consommation_report['total_row']

        self.assertEqual(
            headers,
            ['', 'CU', u' ', ' ', 'Collier', ' ', ' ', 'DIU', u' ', ' ', 'Depo-Provera', ' ', ' ',
             'Jadelle', ' ', ' ', 'Microgynon/Lof.', ' ', ' ', 'Microlut/Ovrette', ' ', ' ',
             'Preservatif Feminin', ' ', ' ', 'Preservatif Masculin', ' ', ' ']
        )
        self.assertEqual(
            rows,
            [
                ['DEBI TIQUET', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 10.0, 'html': 10.0}, '0.00%',
                 {'sort_key': 1.0, 'html': 1.0}, {'sort_key': 4.0, 'html': 4.0}, '25.00%',
                 {'sort_key': 1.0, 'html': 1.0}, {'sort_key': 1.0, 'html': 1.0}, '100.00%',
                 {'sort_key': 24.0, 'html': 24.0}, {'sort_key': 70.0, 'html': 70.0}, '34.29%',
                 {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 5.0, 'html': 5.0}, '80.00%',
                 {'sort_key': 11.0, 'html': 11.0}, {'sort_key': 49.0, 'html': 49.0}, '22.45%',
                 {'sort_key': 17.0, 'html': 17.0}, {'sort_key': 32.0, 'html': 32.0}, '53.12%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 66.0, 'html': 66.0}, {'sort_key': 186.0, 'html': 186.0}, '35.48%'],
                ['DIENDER', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 4.0, 'html': 4.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 1.0, 'html': 1.0}, {'sort_key': 6.0, 'html': 6.0}, '16.67%',
                 {'sort_key': 46.0, 'html': 46.0}, {'sort_key': 173.0, 'html': 173.0}, '26.59%',
                 {'sort_key': 1.0, 'html': 1.0}, {'sort_key': 11.0, 'html': 11.0}, '9.09%',
                 {'sort_key': 64.0, 'html': 64.0}, {'sort_key': 119.0, 'html': 119.0}, '53.78%',
                 {'sort_key': 8.0, 'html': 8.0}, {'sort_key': 26.0, 'html': 26.0}, '30.77%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 10.0, 'html': 10.0}, '0.00%',
                 {'sort_key': 21.0, 'html': 21.0}, {'sort_key': 47.0, 'html': 47.0}, '44.68%'],
                ['DIOGO', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 10.0, 'html': 10.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 3.0, 'html': 3.0}, {'sort_key': 2.0, 'html': 2.0}, '150.00%',
                 {'sort_key': 182.0, 'html': 182.0}, {'sort_key': 242.0, 'html': 242.0}, '75.21%',
                 {'sort_key': 3.0, 'html': 3.0}, {'sort_key': 37.0, 'html': 37.0}, '8.11%',
                 {'sort_key': 89.0, 'html': 89.0}, {'sort_key': 202.0, 'html': 202.0}, '44.06%',
                 {'sort_key': 15.0, 'html': 15.0}, {'sort_key': 63.0, 'html': 63.0}, '23.81%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 20.0, 'html': 20.0}, '0.00%',
                 {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 98.0, 'html': 98.0}, '10.20%'],
                ['GRAND THIES', {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 24.0, 'html': 24.0}, '20.83%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 4.0, 'html': 4.0}, '0.00%',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 4.0, 'html': 4.0}, '125.00%',
                 {'sort_key': 117.0, 'html': 117.0}, {'sort_key': 202.0, 'html': 202.0}, '57.92%',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 14.0, 'html': 14.0}, '35.71%',
                 {'sort_key': 173.0, 'html': 173.0}, {'sort_key': 267.0, 'html': 267.0}, '64.79%',
                 {'sort_key': 57.0, 'html': 57.0}, {'sort_key': 38.0, 'html': 38.0}, '150.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 10.0, 'html': 10.0}, '0.00%',
                 {'sort_key': 70.0, 'html': 70.0}, {'sort_key': 100.0, 'html': 100.0}, '70.00%'],
                ['GUELOR WOLOF', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 4.0, 'html': 4.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 4.0, 'html': 4.0}, '0.00%',
                 {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 62.0, 'html': 62.0}, '16.13%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 8.0, 'html': 8.0}, '0.00%',
                 {'sort_key': 3.0, 'html': 3.0}, {'sort_key': 66.0, 'html': 66.0}, '4.55%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 70.0, 'html': 70.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 60.0, 'html': 60.0}, '0.00%'],
                ['LERANE COLY', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 3.0, 'html': 3.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 2.0, 'html': 2.0}, '0.00%',
                 {'sort_key': 8.0, 'html': 8.0}, {'sort_key': 52.0, 'html': 52.0}, '15.38%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 6.0, 'html': 6.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 42.0, 'html': 42.0}, '0.00%',
                 {'sort_key': 3.0, 'html': 3.0}, {'sort_key': 12.0, 'html': 12.0}, '25.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 100.0, 'html': 100.0}, '0.00%'],
                ['MBANE DAGANA', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 94.0, 'html': 94.0}, {'sort_key': 267.0, 'html': 267.0}, '35.21%',
                 {'sort_key': 3.0, 'html': 3.0}, {'sort_key': 114.0, 'html': 114.0}, '2.63%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['NDIAWAR RICHARD TOLL', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 4.0, 'html': 4.0},
                 '0.00%', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 3.0, 'html': 3.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 58.0, 'html': 58.0}, {'sort_key': 29.0, 'html': 29.0}, '200.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 116.0, 'html': 116.0}, {'sort_key': 65.0, 'html': 65.0}, '178.46%',
                 {'sort_key': 3.0, 'html': 3.0}, {'sort_key': 57.0, 'html': 57.0}, '5.26%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 10.0, 'html': 10.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 100.0, 'html': 100.0}, '0.00%'],
                ['NIANGUE DIAW', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 1.0, 'html': 1.0}, {'sort_key': 2.0, 'html': 2.0}, '50.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 11.0, 'html': 11.0}, '0.00%',
                 {'sort_key': 69.0, 'html': 69.0}, {'sort_key': 77.0, 'html': 77.0}, '89.61%',
                 {'sort_key': 2.0, 'html': 2.0}, {'sort_key': 21.0, 'html': 21.0}, '9.52%',
                 {'sort_key': 48.0, 'html': 48.0}, {'sort_key': 127.0, 'html': 127.0}, '37.80%',
                 {'sort_key': 9.0, 'html': 9.0}, {'sort_key': 65.0, 'html': 65.0}, '13.85%',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 16.0, 'html': 16.0}, '31.25%',
                 {'sort_key': 32.0, 'html': 32.0}, {'sort_key': 106.0, 'html': 106.0}, '30.19%'],
                ['PASSY', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.00%'],
                ['PS CAMP MILITAIRE', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0},
                 '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 4.0, 'html': 4.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 8.0, 'html': 8.0}, '0.00%',
                 {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 117.0, 'html': 117.0}, '3.42%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 9.0, 'html': 9.0}, '0.00%',
                 {'sort_key': 100.0, 'html': 100.0}, {'sort_key': 0.0, 'html': 0.0}, '10000.00%',
                 {'sort_key': 3.0, 'html': 3.0}, {'sort_key': 158.0, 'html': 158.0}, '1.90%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 10.0, 'html': 10.0}, '0.00%',
                 {'sort_key': 234.0, 'html': 234.0}, {'sort_key': 546.0, 'html': 546.0}, '42.86%'],
                ['PS DE DOUMGA OURO ALPHA', {'sort_key': 1.0, 'html': 1.0}, {'sort_key': 4.0, 'html': 4.0},
                 '25.00%', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 2.0, 'html': 2.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 2.0, 'html': 2.0}, '0.00%',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 83.0, 'html': 83.0}, '6.02%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 30.0, 'html': 30.0}, {'sort_key': 90.0, 'html': 90.0}, '33.33%',
                 {'sort_key': 12.0, 'html': 12.0}, {'sort_key': 18.0, 'html': 18.0}, '66.67%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 10.0, 'html': 10.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 100.0, 'html': 100.0}, '0.00%'],
                ['PS DE KOBILO', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 4.0, 'html': 4.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 2.0, 'html': 2.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 2.0, 'html': 2.0}, '0.00%',
                 {'sort_key': 9.0, 'html': 9.0}, {'sort_key': 32.0, 'html': 32.0}, '28.12%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 19.0, 'html': 19.0}, {'sort_key': 9.0, 'html': 9.0}, '211.11%',
                 {'sort_key': 9.0, 'html': 9.0}, {'sort_key': 26.0, 'html': 26.0}, '34.62%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 10.0, 'html': 10.0}, '0.00%',
                 {'sort_key': 22.0, 'html': 22.0}, {'sort_key': 74.0, 'html': 74.0}, '29.73%'],
                ['PS DIOKOUL WAGUE', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 7.0, 'html': 7.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 28.0, 'html': 28.0}, {'sort_key': 80.0, 'html': 80.0}, '35.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 15.0, 'html': 15.0}, '0.00%',
                 {'sort_key': 33.0, 'html': 33.0}, {'sort_key': 130.0, 'html': 130.0}, '25.38%',
                 {'sort_key': 21.0, 'html': 21.0}, {'sort_key': 33.0, 'html': 33.0}, '63.64%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 84.0, 'html': 84.0}, '0.00%'],
                ['PS NGOR', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 4.0, 'html': 4.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 5.0, 'html': 5.0}, '0.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 3.0, 'html': 3.0}, '0.00%',
                 {'sort_key': 100.0, 'html': 100.0}, {'sort_key': 318.0, 'html': 318.0}, '31.45%',
                 {'sort_key': 6.0, 'html': 6.0}, {'sort_key': 28.0, 'html': 28.0}, '21.43%',
                 {'sort_key': 179.0, 'html': 179.0}, {'sort_key': 345.0, 'html': 345.0}, '51.88%',
                 {'sort_key': 13.0, 'html': 13.0}, {'sort_key': 96.0, 'html': 96.0}, '13.54%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 10.0, 'html': 10.0}, '0.00%',
                 {'sort_key': 6.0, 'html': 6.0}, {'sort_key': 144.0, 'html': 144.0}, '4.17%'],
                ['PS PLLES ASS. UNITE 12', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 8.0, 'html': 8.0},
                 '0.00%', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 4.0, 'html': 4.0}, '0.00%',
                 {'sort_key': 13.0, 'html': 13.0}, {'sort_key': 1.0, 'html': 1.0}, '1300.00%',
                 {'sort_key': 139.0, 'html': 139.0}, {'sort_key': 433.0, 'html': 433.0}, '32.10%',
                 {'sort_key': 16.0, 'html': 16.0}, {'sort_key': 17.0, 'html': 17.0}, '94.12%',
                 {'sort_key': 215.0, 'html': 215.0}, {'sort_key': 403.0, 'html': 403.0}, '53.35%',
                 {'sort_key': 29.0, 'html': 29.0}, {'sort_key': 171.0, 'html': 171.0}, '16.96%',
                 {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 0.0, 'html': 0.0}, '1000.00%',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 211.0, 'html': 211.0}, '0.00%']
            ],
        )
        self.assertEqual(
            total_row,
            ['', 6.0, 97.0, '6.19%', 2.0, 49.0, '4.08%', 23.0, 56.0, '41.07%', 799.0, 1970.0,
             '40.56%', 37.0, 186.0, '19.89%', 1174.0, 2181.0, '53.83%', 202.0, 979.0, '20.63%', 15.0,
             126.0, '11.90%', 461.0, 1956.0, '23.57%']
        )

    def test_nombre_data_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '1991b4dfe166335e342f28134b85fcac',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        nombre_data_report = tableu_de_board_report2_report.report_context['reports'][6]['report_table']
        headers = nombre_data_report['headers'].as_export_table[0]
        rows = nombre_data_report['rows']
        total_row = nombre_data_report['total_row']

        self.assertEqual(
            headers,
            ['', 'CU', u' ', ' ', 'Collier', ' ', ' ', 'DIU', u' ', ' ', 'Depo-Provera', ' ', ' ',
             'Jadelle', ' ', ' ', 'Microgynon/Lof.', ' ', ' ', 'Microlut/Ovrette', ' ', ' ',
             'Preservatif Feminin', ' ', ' ', 'Preservatif Masculin', ' ', ' ']
        )
        self.assertEqual(
            rows,
            [
                ['DEBI TIQUET', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['DIENDER', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['DIOGO', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['GRAND THIES', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['GUELOR WOLOF', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['LERANE COLY', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['MBANE DAGANA', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['NDIAWAR RICHARD TOLL', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0},
                 '0.000', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['NIANGUE DIAW', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['PASSY', {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 1.0, 'html': 1.0}, '5.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 1.0, 'html': 1.0}, '5.000',
                 {'sort_key': 77.0, 'html': 77.0}, {'sort_key': 5.0, 'html': 5.0}, '15.400',
                 {'sort_key': 11.0, 'html': 11.0}, {'sort_key': 1.0, 'html': 1.0}, '11.000',
                 {'sort_key': 42.0, 'html': 42.0}, {'sort_key': 3.0, 'html': 3.0}, '14.000',
                 {'sort_key': 30.0, 'html': 30.0}, {'sort_key': 1.0, 'html': 1.0}, '30.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 1.0, 'html': 1.0}, '5.000',
                 {'sort_key': 100.0, 'html': 100.0}, {'sort_key': 1.0, 'html': 1.0}, '100.000'],
                ['PS CAMP MILITAIRE', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0},
                 '0.000', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['PS DE DOUMGA OURO ALPHA', {'sort_key': 0.0, 'html': 0.0},
                 {'sort_key': 0.0, 'html': 0.0},
                 '0.000', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['PS DE KOBILO', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['PS DIOKOUL WAGUE', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0},
                 '0.000', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['PS NGOR', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['PS PLLES ASS. UNITE 12', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0},
                 '0.000', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000']
            ],
        )
        self.assertEqual(
            total_row,
            ['', 5.0, 1.0, '5.000', 0, 0, '0.000', 5.0, 1.0, '5.000', 77.0, 5.0, '15.400', 11.0, 1.0,
             '11.000', 42.0, 3.0, '14.000', 30.0, 1.0, '30.000', 5.0, 1.0, '5.000', 100.0, 1.0, '100.000']
        )

    def test_nombre_data_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        nombre_data_report = tableu_de_board_report2_report.report_context['reports'][6]['report_table']
        headers = nombre_data_report['headers'].as_export_table[0]
        rows = nombre_data_report['rows']
        total_row = nombre_data_report['total_row']

        self.assertEqual(
            headers,
            ['', 'CU', u' ', ' ', 'Collier', ' ', ' ', 'DIU', u' ', ' ', 'Depo-Provera', ' ', ' ',
             'Jadelle', ' ', ' ', 'Microgynon/Lof.', ' ', ' ', 'Microlut/Ovrette', ' ', ' ',
             'Preservatif Feminin', ' ', ' ', 'Preservatif Masculin', ' ', ' ']
        )
        self.assertEqual(
            rows,
            [
                ['DEBI TIQUET', {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 9.0, 'html': 9.0}, '1.111',
                 {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 1.0, 'html': 1.0}, '4.000',
                 {'sort_key': 1.0, 'html': 1.0}, {'sort_key': 1.0, 'html': 1.0}, '1.000',
                 {'sort_key': 70.0, 'html': 70.0}, {'sort_key': 1.0, 'html': 1.0}, '70.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 1.0, 'html': 1.0}, '5.000',
                 {'sort_key': 49.0, 'html': 49.0}, {'sort_key': 26.0, 'html': 26.0}, '1.885',
                 {'sort_key': 32.0, 'html': 32.0}, {'sort_key': 1.0, 'html': 1.0}, '32.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 3.0, 'html': 3.0}, '1.667',
                 {'sort_key': 186.0, 'html': 186.0}, {'sort_key': 1.0, 'html': 1.0}, '186.000'],
                ['DIENDER', {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 0.0, 'html': 0.0}, '4.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 0.0, 'html': 0.0}, '5.000',
                 {'sort_key': 6.0, 'html': 6.0}, {'sort_key': 0.0, 'html': 0.0}, '6.000',
                 {'sort_key': 173.0, 'html': 173.0}, {'sort_key': 0.0, 'html': 0.0}, '173.000',
                 {'sort_key': 11.0, 'html': 11.0}, {'sort_key': 0.0, 'html': 0.0}, '11.000',
                 {'sort_key': 179.0, 'html': 179.0}, {'sort_key': 0.0, 'html': 0.0}, '179.000',
                 {'sort_key': 26.0, 'html': 26.0}, {'sort_key': 0.0, 'html': 0.0}, '26.000',
                 {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 0.0, 'html': 0.0}, '10.000',
                 {'sort_key': 147.0, 'html': 147.0}, {'sort_key': 0.0, 'html': 0.0}, '147.000'],
                ['DIOGO', {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 0.0, 'html': 0.0}, '10.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 0.0, 'html': 0.0}, '5.000',
                 {'sort_key': 8.0, 'html': 8.0}, {'sort_key': 0.0, 'html': 0.0}, '8.000',
                 {'sort_key': 542.0, 'html': 542.0}, {'sort_key': 4.0, 'html': 4.0}, '135.500',
                 {'sort_key': 37.0, 'html': 37.0}, {'sort_key': 0.0, 'html': 0.0}, '37.000',
                 {'sort_key': 262.0, 'html': 262.0}, {'sort_key': 2.0, 'html': 2.0}, '131.000',
                 {'sort_key': 63.0, 'html': 63.0}, {'sort_key': 0.0, 'html': 0.0}, '63.000',
                 {'sort_key': 20.0, 'html': 20.0}, {'sort_key': 0.0, 'html': 0.0}, '20.000',
                 {'sort_key': 98.0, 'html': 98.0}, {'sort_key': 1.0, 'html': 1.0}, '98.000'],
                ['GRAND THIES', {'sort_key': 24.0, 'html': 24.0}, {'sort_key': 0.0, 'html': 0.0}, '24.000',
                 {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 0.0, 'html': 0.0}, '4.000',
                 {'sort_key': 14.0, 'html': 14.0}, {'sort_key': 0.0, 'html': 0.0}, '14.000',
                 {'sort_key': 352.0, 'html': 352.0}, {'sort_key': 0.0, 'html': 0.0}, '352.000',
                 {'sort_key': 14.0, 'html': 14.0}, {'sort_key': 0.0, 'html': 0.0}, '14.000',
                 {'sort_key': 507.0, 'html': 507.0}, {'sort_key': 0.0, 'html': 0.0}, '507.000',
                 {'sort_key': 158.0, 'html': 158.0}, {'sort_key': 0.0, 'html': 0.0}, '158.000',
                 {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 0.0, 'html': 0.0}, '10.000',
                 {'sort_key': 200.0, 'html': 200.0}, {'sort_key': 0.0, 'html': 0.0}, '200.000'],
                ['GUELOR WOLOF', {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 0.0, 'html': 0.0}, '5.000',
                 {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 0.0, 'html': 0.0}, '4.000',
                 {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 0.0, 'html': 0.0}, '4.000',
                 {'sort_key': 62.0, 'html': 62.0}, {'sort_key': 0.0, 'html': 0.0}, '62.000',
                 {'sort_key': 8.0, 'html': 8.0}, {'sort_key': 0.0, 'html': 0.0}, '8.000',
                 {'sort_key': 66.0, 'html': 66.0}, {'sort_key': 0.0, 'html': 0.0}, '66.000',
                 {'sort_key': 70.0, 'html': 70.0}, {'sort_key': 0.0, 'html': 0.0}, '70.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 0.0, 'html': 0.0}, '5.000',
                 {'sort_key': 60.0, 'html': 60.0}, {'sort_key': 0.0, 'html': 0.0}, '60.000'],
                ['LERANE COLY', {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 1.0, 'html': 1.0}, '5.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 1.0, 'html': 1.0}, '5.000',
                 {'sort_key': 77.0, 'html': 77.0}, {'sort_key': 5.0, 'html': 5.0}, '15.400',
                 {'sort_key': 11.0, 'html': 11.0}, {'sort_key': 1.0, 'html': 1.0}, '11.000',
                 {'sort_key': 42.0, 'html': 42.0}, {'sort_key': 3.0, 'html': 3.0}, '14.000',
                 {'sort_key': 30.0, 'html': 30.0}, {'sort_key': 1.0, 'html': 1.0}, '30.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 1.0, 'html': 1.0}, '5.000',
                 {'sort_key': 100.0, 'html': 100.0}, {'sort_key': 1.0, 'html': 1.0}, '100.000'],
                ['MBANE DAGANA', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 267.0, 'html': 267.0}, {'sort_key': 89.0, 'html': 89.0}, '3.000',
                 {'sort_key': 114.0, 'html': 114.0}, {'sort_key': 33.0, 'html': 33.0}, '3.455',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['NDIAWAR RICHARD TOLL', {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 86.0, 'html': 86.0},
                 '0.047', {'sort_key': 3.0, 'html': 3.0}, {'sort_key': 1.0, 'html': 1.0}, '3.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 1.0, 'html': 1.0}, '5.000',
                 {'sort_key': 29.0, 'html': 29.0}, {'sort_key': 1.0, 'html': 1.0}, '29.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 1.0, 'html': 1.0}, '5.000',
                 {'sort_key': 65.0, 'html': 65.0}, {'sort_key': 36.0, 'html': 36.0}, '1.806',
                 {'sort_key': 57.0, 'html': 57.0}, {'sort_key': 1.0, 'html': 1.0}, '57.000',
                 {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 1.0, 'html': 1.0}, '10.000',
                 {'sort_key': 100.0, 'html': 100.0}, {'sort_key': 1.0, 'html': 1.0}, '100.000'],
                ['NIANGUE DIAW', {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 45.0, 'html': 45.0}, '0.111',
                 {'sort_key': 3.0, 'html': 3.0}, {'sort_key': 1.0, 'html': 1.0}, '3.000',
                 {'sort_key': 11.0, 'html': 11.0}, {'sort_key': 1.0, 'html': 1.0}, '11.000',
                 {'sort_key': 177.0, 'html': 177.0}, {'sort_key': 1.0, 'html': 1.0}, '177.000',
                 {'sort_key': 24.0, 'html': 24.0}, {'sort_key': 1.0, 'html': 1.0}, '24.000',
                 {'sort_key': 135.0, 'html': 135.0}, {'sort_key': 55.0, 'html': 55.0}, '2.455',
                 {'sort_key': 83.0, 'html': 83.0}, {'sort_key': 8.0, 'html': 8.0}, '10.375',
                 {'sort_key': 16.0, 'html': 16.0}, {'sort_key': 27.0, 'html': 27.0}, '0.593',
                 {'sort_key': 106.0, 'html': 106.0}, {'sort_key': 1.0, 'html': 1.0}, '106.000'],
                ['PASSY', {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000',
                 {'sort_key': 0.0, 'html': 0.0}, {'sort_key': 0.0, 'html': 0.0}, '0.000'],
                ['PS CAMP MILITAIRE', {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 0.0, 'html': 0.0},
                 '5.000',
                 {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 0.0, 'html': 0.0}, '4.000',
                 {'sort_key': 8.0, 'html': 8.0}, {'sort_key': 0.0, 'html': 0.0}, '8.000',
                 {'sort_key': 117.0, 'html': 117.0}, {'sort_key': 0.0, 'html': 0.0}, '117.000',
                 {'sort_key': 9.0, 'html': 9.0}, {'sort_key': 0.0, 'html': 0.0}, '9.000',
                 {'sort_key': 100.0, 'html': 100.0}, {'sort_key': 0.0, 'html': 0.0}, '100.000',
                 {'sort_key': 158.0, 'html': 158.0}, {'sort_key': 0.0, 'html': 0.0}, '158.000',
                 {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 0.0, 'html': 0.0}, '10.000',
                 {'sort_key': 546.0, 'html': 546.0}, {'sort_key': 0.0, 'html': 0.0}, '546.000'],
                ['PS DE DOUMGA OURO ALPHA', {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 0.0, 'html': 0.0},
                 '4.000', {'sort_key': 2.0, 'html': 2.0}, {'sort_key': 0.0, 'html': 0.0}, '2.000',
                 {'sort_key': 2.0, 'html': 2.0}, {'sort_key': 0.0, 'html': 0.0}, '2.000',
                 {'sort_key': 83.0, 'html': 83.0}, {'sort_key': 0.0, 'html': 0.0}, '83.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 0.0, 'html': 0.0}, '5.000',
                 {'sort_key': 90.0, 'html': 90.0}, {'sort_key': 1.0, 'html': 1.0}, '90.000',
                 {'sort_key': 36.0, 'html': 36.0}, {'sort_key': 0.0, 'html': 0.0}, '36.000',
                 {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 0.0, 'html': 0.0}, '10.000',
                 {'sort_key': 100.0, 'html': 100.0}, {'sort_key': 0.0, 'html': 0.0}, '100.000'],
                ['PS DE KOBILO', {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 0.0, 'html': 0.0}, '4.000',
                 {'sort_key': 2.0, 'html': 2.0}, {'sort_key': 0.0, 'html': 0.0}, '2.000',
                 {'sort_key': 2.0, 'html': 2.0}, {'sort_key': 0.0, 'html': 0.0}, '2.000',
                 {'sort_key': 32.0, 'html': 32.0}, {'sort_key': 0.0, 'html': 0.0}, '32.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 0.0, 'html': 0.0}, '5.000',
                 {'sort_key': 57.0, 'html': 57.0}, {'sort_key': 0.0, 'html': 0.0}, '57.000',
                 {'sort_key': 26.0, 'html': 26.0}, {'sort_key': 0.0, 'html': 0.0}, '26.000',
                 {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 0.0, 'html': 0.0}, '10.000',
                 {'sort_key': 74.0, 'html': 74.0}, {'sort_key': 0.0, 'html': 0.0}, '74.000'],
                ['PS DIOKOUL WAGUE', {'sort_key': 7.0, 'html': 7.0}, {'sort_key': 0.0, 'html': 0.0}, '7.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 0.0, 'html': 0.0}, '5.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 0.0, 'html': 0.0}, '5.000',
                 {'sort_key': 180.0, 'html': 180.0}, {'sort_key': 0.0, 'html': 0.0}, '180.000',
                 {'sort_key': 15.0, 'html': 15.0}, {'sort_key': 0.0, 'html': 0.0}, '15.000',
                 {'sort_key': 130.0, 'html': 130.0}, {'sort_key': 0.0, 'html': 0.0}, '130.000',
                 {'sort_key': 63.0, 'html': 63.0}, {'sort_key': 0.0, 'html': 0.0}, '63.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 0.0, 'html': 0.0}, '5.000',
                 {'sort_key': 84.0, 'html': 84.0}, {'sort_key': 0.0, 'html': 0.0}, '84.000'],
                ['PS NGOR', {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 0.0, 'html': 0.0}, '4.000',
                 {'sort_key': 5.0, 'html': 5.0}, {'sort_key': 0.0, 'html': 0.0}, '5.000',
                 {'sort_key': 3.0, 'html': 3.0}, {'sort_key': 0.0, 'html': 0.0}, '3.000',
                 {'sort_key': 418.0, 'html': 418.0}, {'sort_key': 0.0, 'html': 0.0}, '418.000',
                 {'sort_key': 28.0, 'html': 28.0}, {'sort_key': 0.0, 'html': 0.0}, '28.000',
                 {'sort_key': 545.0, 'html': 545.0}, {'sort_key': 0.0, 'html': 0.0}, '545.000',
                 {'sort_key': 96.0, 'html': 96.0}, {'sort_key': 0.0, 'html': 0.0}, '96.000',
                 {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 0.0, 'html': 0.0}, '10.000',
                 {'sort_key': 144.0, 'html': 144.0}, {'sort_key': 0.0, 'html': 0.0}, '144.000'],
                ['PS PLLES ASS. UNITE 12', {'sort_key': 8.0, 'html': 8.0}, {'sort_key': 0.0, 'html': 0.0},
                 '8.000', {'sort_key': 4.0, 'html': 4.0}, {'sort_key': 0.0, 'html': 0.0}, '4.000',
                 {'sort_key': 31.0, 'html': 31.0}, {'sort_key': 0.0, 'html': 0.0}, '31.000',
                 {'sort_key': 433.0, 'html': 433.0}, {'sort_key': 0.0, 'html': 0.0}, '433.000',
                 {'sort_key': 37.0, 'html': 37.0}, {'sort_key': 0.0, 'html': 0.0}, '37.000',
                 {'sort_key': 503.0, 'html': 503.0}, {'sort_key': 0.0, 'html': 0.0}, '503.000',
                 {'sort_key': 171.0, 'html': 171.0}, {'sort_key': 0.0, 'html': 0.0}, '171.000',
                 {'sort_key': 10.0, 'html': 10.0}, {'sort_key': 0.0, 'html': 0.0}, '10.000',
                 {'sort_key': 211.0, 'html': 211.0}, {'sort_key': 0.0, 'html': 0.0}, '211.000']
            ],
        )
        self.assertEqual(
            total_row,
            ['', 99.0, 141.0, '0.702', 50.0, 3.0, '16.667', 105.0, 4.0, '26.250', 2745.0, 12.0, '228.750',
             214.0, 4.0, '53.500', 2997.0, 212.0, '14.137', 1183.0, 44.0, '26.886', 136.0, 32.0, '4.250',
             2156.0, 5.0, '431.200']
        )

    def test_gestion_de_LIPM_taux_de_ruptures_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '1991b4dfe166335e342f28134b85fcac',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        gestion_de_LIPM_taux_de_ruptures_report = \
            tableu_de_board_report2_report.report_context['reports'][7]['report_table']
        headers = gestion_de_LIPM_taux_de_ruptures_report['headers'].as_export_table[0]
        rows = gestion_de_LIPM_taux_de_ruptures_report['rows']
        total_row = gestion_de_LIPM_taux_de_ruptures_report['total_row']

        self.assertEqual(
            headers,
            ['District', 'Collier', 'CU', u'Depo-Provera', 'DIU', u'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [['NIAKHAR', 0, 0, 0, 0, 0, 0, 0, 0, 0], ['PASSY', 0, 0, 0, 0, 0, 0, 0, 0, 0],
             ['FATICK', 0, 0, 0, 0, 0, 0, 0, 0, 0]],
        )
        self.assertEqual(
            total_row,
            ['Taux rupture', '(0/3) 0.00%', '(0/3) 0.00%', '(0/3) 0.00%', '(0/3) 0.00%', '(0/3) 0.00%',
             '(0/3) 0.00%', '(0/3) 0.00%', '(0/3) 0.00%', '(0/3) 0.00%']
        )

    def test_gestion_de_LIPM_taux_de_ruptures_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        gestion_de_LIPM_taux_de_ruptures_report = tableu_de_board_report2_report.report_context['reports'][7][
            'report_table']
        headers = gestion_de_LIPM_taux_de_ruptures_report['headers'].as_export_table[0]
        rows = gestion_de_LIPM_taux_de_ruptures_report['rows']
        total_row = gestion_de_LIPM_taux_de_ruptures_report['total_row']

        self.assertEqual(
            headers,
            ['PPS', 'Collier', 'CU', u'Depo-Provera', 'DIU', u'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [
                ['NDAIYE NDIAYE OUOLOF', 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['PATAR SINE', 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['NDIONGOLOR', 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['NIASSENE', 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['PEULGHA', 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['MBELLONGOUTTE', 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['LERANE COLY', 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['SENGHOR', 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['DJILOR SALOUM', 0, 0, 0, 0, 0, 0, 0, 0, 0]
            ],
        )
        self.assertEqual(
            total_row,
            ['Taux rupture', '(0/9) 0.00%', '(0/9) 0.00%', '(0/9) 0.00%', '(0/9) 0.00%', '(0/9) 0.00%',
             '(0/9) 0.00%', '(0/9) 0.00%', '(0/9) 0.00%', '(0/9) 0.00%']
        )

    def test_z_duree_data_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2015-06-01',
            'enddate': '2015-07-31',
            'location_id': '6ed1f958fccd1b8202e8e30851a2b326',
        }
        mock.datespan = DateSpan(datetime.datetime(2015, 6, 1), datetime.datetime(2015, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        duree_data_report = tableu_de_board_report2_report.report_context['reports'][8]['report_table']
        headers = duree_data_report['headers'].as_export_table[0]
        rows = duree_data_report['rows']
        total_row = duree_data_report['total_row']
        self.assertEqual(
            headers,
            ['District', 'Retards de livraison (jours)']
        )
        self.assertEqual(
            rows,
            [['KIDIRA', '0.00'], ['KOUMPENTOUM', '0.00'], ['MAKA COULIBANTANG', '0.00'],
             ['TAMBACOUNDA', '0.00']],
        )
        self.assertEqual(
            total_row,
            ['Moyenne Region', '0.00']
        )

    def test_z_duree_data_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2015-06-01',
            'enddate': '2015-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2015, 6, 1), datetime.datetime(2015, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        duree_data_report = tableu_de_board_report2_report.report_context['reports'][8]['report_table']
        headers = duree_data_report['headers'].as_export_table[0]
        rows = duree_data_report['rows']
        total_row = duree_data_report['total_row']
        self.assertEqual(
            headers,
            ['District', 'Retards de livraison (jours)']
        )
        self.assertEqual(
            rows,
            [
                ['BAMBEY', '0.00'], ['DIOURBEL', '0.00'], ['Dakar Centre', '0.00'], ['Dakar Sud', '0.00'],
                ['Diamniadio', '0.00'], ['Guinguineo', '0.00'], ['KAFFRINE', '0.00'], ['KIDIRA', '0.00'],
                ['KOUMPENTOUM', '0.00'], ['Kaolack', '0.00'], ['Kebemer', '0.00'], ['Keur Massar', '0.00'],
                ['Keur Momar Sarr', '0.00'], ['Kolda', '0.00'], ['Linguere', '0.00'],
                ['MAKA COULIBANTANG', '0.00'], ['MALEN HODDAR', '0.00'], ['MBACKE', '0.00'],
                ['MBIRKILANE', '0.00'], ['Matam', '0.00'], ['Mbao', '0.00'],
                ['Medina Yoro Foulah', '0.00'],
                ['Oussouye', '0.00'], ['Podor', '0.00'], ['SARAYA', '0.00'], ['Saint Louis', '0.00'],
                ['Sakal', '0.00'], ['TAMBACOUNDA', '0.00'], ['TOUBA', '0.00'], ['Thilogne', '0.00'],
                ['Thionck Essyl', '0.00']],
        )
        self.assertEqual(
            total_row,
            ['Moyenne Region', '0.00']
        )

    def test_z_recouvrement_des_couts_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2015-06-01',
            'enddate': '2015-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2015, 6, 1), datetime.datetime(2015, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        recouvrement_des_couts_report = tableu_de_board_report2_report.report_context['reports'][9]['report_table']
        headers = recouvrement_des_couts_report['headers'].as_export_table[0]
        rows = recouvrement_des_couts_report['rows']
        total_row = recouvrement_des_couts_report['total_row']

        self.assertEqual(
            headers,
            ['District', 'Montant d\xfb', 'Montant pay\xe9', 'Pay\xe9 dans le 30 jours',
             'Pay\xe9 dans le 3 mois', 'Pay\xe9 dans l`ann\xe8e']
        )
        self.assertEqual(
            rows,
            [
                ['BAKEL', 0, 0, 1, 1, 1], ['BAMBEY', 217072, 217072, 0, 1, 1],
                ['Bignona', 0, 0, 1, 1, 1], ['DIANKHE MAKHA', 0, 0, 1, 1, 1],
                ['Diamniadio', 195867, 195867, 1, 1, 1], ['Diouloulou', 48791, 48791, 2, 2, 2],
                ['GOUDIRY', 0, 0, 0, 0, 1], ['Guediawaye', 566171, 0, 0, 0, 0],
                ['KAFFRINE', 269204, 269204, 1, 1, 1], ['Kanel', 122449, 122449, 1, 1, 1],
                ['Kaolack', 511713, 0, 0, 1, 1], ['Kebemer', 201778, 201778, 1, 1, 1],
                ['Linguere', 163083, 0, 0, 0, 0], ['Louga', 147611, 147611, 1, 1, 1],
                ['MBACKE', 170948, 0, 0, 0, 0], ['Matam', 203910, 203910, 1, 1, 1],
                ['Mbao', 860698, 860698, 1, 1, 1], ['Ndoffane', 312728, 148725, 0, 1, 1],
                ['Oussouye', 57236, 57236, 1, 1, 1], ['Podor', 193364, 193364, 1, 1, 1],
                ['P\xe9t\xe9', 137760, 137760, 1, 1, 1], ['SALEMATA', 25582, 25582, 1, 1, 1],
                ['Saint Louis', 498551, 498551, 1, 1, 1], ['Sakal', 86758, 86758, 1, 1, 1],
                ['Velingara', 528912, 528912, 0, 2, 2]
            ],
        )
        self.assertEqual(
            total_row,
            ['Total Region', 5520186, 3944268, 18, 23, 24]
        )

    def test_z_recouvrement_des_couts_report_countrywide(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2015-06-01',
            'enddate': '2015-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2015, 6, 1), datetime.datetime(2015, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        recouvrement_des_couts_report = tableu_de_board_report2_report.report_context['reports'][9]['report_table']
        headers = recouvrement_des_couts_report['headers'].as_export_table[0]
        rows = recouvrement_des_couts_report['rows']
        total_row = recouvrement_des_couts_report['total_row']

        self.assertEqual(
            headers,
            ['District', 'Montant d\xfb', 'Montant pay\xe9', 'Pay\xe9 dans le 30 jours',
             'Pay\xe9 dans le 3 mois', 'Pay\xe9 dans l`ann\xe8e']
        )
        self.assertEqual(
            rows,
            [
                ['BAKEL', 0, 0, 1, 1, 1], ['BAMBEY', 217072, 217072, 0, 1, 1],
                ['Bignona', 0, 0, 1, 1, 1], ['DIANKHE MAKHA', 0, 0, 1, 1, 1],
                ['Diamniadio', 195867, 195867, 1, 1, 1], ['Diouloulou', 48791, 48791, 2, 2, 2],
                ['GOUDIRY', 0, 0, 0, 0, 1], ['Guediawaye', 566171, 0, 0, 0, 0],
                ['KAFFRINE', 269204, 269204, 1, 1, 1], ['Kanel', 122449, 122449, 1, 1, 1],
                ['Kaolack', 511713, 0, 0, 1, 1], ['Kebemer', 201778, 201778, 1, 1, 1],
                ['Linguere', 163083, 0, 0, 0, 0], ['Louga', 147611, 147611, 1, 1, 1],
                ['MBACKE', 170948, 0, 0, 0, 0], ['Matam', 203910, 203910, 1, 1, 1],
                ['Mbao', 860698, 860698, 1, 1, 1], ['Ndoffane', 312728, 148725, 0, 1, 1],
                ['Oussouye', 57236, 57236, 1, 1, 1], ['Podor', 193364, 193364, 1, 1, 1],
                ['P\xe9t\xe9', 137760, 137760, 1, 1, 1], ['SALEMATA', 25582, 25582, 1, 1, 1],
                ['Saint Louis', 498551, 498551, 1, 1, 1], ['Sakal', 86758, 86758, 1, 1, 1],
                ['Velingara', 528912, 528912, 0, 2, 2]
            ],
        )
        self.assertEqual(
            total_row,
            ['Total Region', 5520186, 3944268, 18, 23, 24]
        )
