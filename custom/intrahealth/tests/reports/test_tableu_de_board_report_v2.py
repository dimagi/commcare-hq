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
            ['District', 'CU', 'DIU', 'Depo-Provera', 'Jadelle', 'Microgynon/Lof.', 'Microlut/Ovrette',
             'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [['PASSY', 1, 1, 1, 1, 1, 1, 1, 1], ['Total', 1, 1, 1, 1, 1, 1, 1, 1]],
        )
        self.assertEqual(
            total_row,
            ['Taux rupture', '(1/1) 100.00%', '(1/1) 100.00%', '(1/1) 100.00%', '(1/1) 100.00%',
             '(1/1) 100.00%', '(1/1) 100.00%', '(1/1) 100.00%', '(1/1) 100.00%']
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
            ['PPS', 'CU', 'Collier', 'DIU', 'Depo-Provera', 'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [['DEBI TIQUET', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['DIENDER', 1, 1, 1, 1, 1, 1, 1, 1, 1],
             ['DIOGO', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['GRAND THIES', 1, 1, 1, 1, 1, 1, 1, 1, 1],
             ['GUELOR WOLOF', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['LERANE COLY', 1, 0, 1, 1, 1, 1, 1, 1, 1],
             ['MBANE DAGANA', 0, 0, 0, 0, 0, 1, 1, 0, 0], ['NDIAWAR RICHARD TOLL', 1, 1, 1, 1, 1, 1, 1, 1, 1],
             ['NIANGUE DIAW', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['PS CAMP MILITAIRE', 1, 1, 1, 1, 1, 1, 1, 1, 1],
             ['PS DE DOUMGA OURO ALPHA', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['PS DE KOBILO', 1, 1, 1, 1, 1, 1, 1, 1, 1],
             ['PS DIOKOUL WAGUE', 1, 1, 1, 1, 1, 1, 1, 1, 1], ['PS NGOR', 1, 1, 1, 1, 1, 1, 1, 1, 1],
             ['PS PLLES ASS. UNITE 12', 1, 1, 1, 1, 1, 1, 1, 1, 1],
             ['Total', 14, 13, 14, 14, 14, 15, 15, 14, 14]],
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
            ['District', 'CU', 'DIU', 'Depo-Provera', 'Jadelle', 'Microgynon/Lof.', 'Microlut/Ovrette',
             'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [['PASSY', 0, 0, 8, 0, 0, 3, 0, 0]]
        )
        self.assertEqual(
            total_row,
            ['Total', 0, 0, 8, 0, 0, 3, 0, 0]
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
            ['PPS', 'CU', 'Collier', 'DIU', 'Depo-Provera', 'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [['DEBI TIQUET', 0, 1, 1, 24, 4, 11, 17, 0, 66],
             ['DIENDER', 0, 0, 1, 46, 1, 64, 8, 0, 21],
             ['DIOGO', 0, 0, 3, 182, 3, 89, 15, 0, 10],
             ['GRAND THIES', 5, 0, 5, 117, 5, 173, 57, 0, 70],
             ['GUELOR WOLOF', 0, 0, 0, 10, 0, 3, 0, 0, 0],
             ['LERANE COLY', 0, 0, 0, 8, 0, 0, 3, 0, 0], ['MBANE DAGANA', 0, 0, 0, 0, 0, 94, 3, 0, 0],
             ['NDIAWAR RICHARD TOLL', 0, 0, 0, 58, 0, 116, 3, 0, 0],
             ['NIANGUE DIAW', 0, 1, 0, 69, 2, 48, 9, 5, 32],
             ['PS CAMP MILITAIRE', 0, 0, 0, 4, 0, 100, 3, 0, 234],
             ['PS DE DOUMGA OURO ALPHA', 1, 0, 0, 5, 0, 30, 12, 0, 0],
             ['PS DE KOBILO', 0, 0, 0, 9, 0, 19, 9, 0, 22],
             ['PS DIOKOUL WAGUE', 0, 0, 0, 28, 0, 33, 21, 0, 0],
             ['PS NGOR', 0, 0, 0, 100, 6, 179, 13, 0, 6],
             ['PS PLLES ASS. UNITE 12', 0, 0, 13, 139, 16, 215, 29, 10, 0]]
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
            ['', 'CU', ' ', ' ', 'DIU', ' ', ' ', 'Depo-Provera', ' ', ' ', 'Jadelle', ' ', ' ',
             'Microgynon/Lof.', ' ', ' ', 'Microlut/Ovrette', ' ', ' ', 'Preservatif Feminin', ' ', ' ',
             'Preservatif Masculin', ' ', ' ']
        )
        self.assertEqual(
            rows,
            [['PASSY', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '3.00', 'html': '3.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '2.00', 'html': '2.00'},
              '0.00%', {'sort_key': '8.00', 'html': '8.00'}, {'sort_key': '52.00', 'html': '52.00'},
              '15.38%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '6.00', 'html': '6.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '42.00', 'html': '42.00'},
              '0.00%', {'sort_key': '3.00', 'html': '3.00'}, {'sort_key': '12.00', 'html': '12.00'},
              '25.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '100.00', 'html': '100.00'},
              '0.00%']],
        )
        self.assertEqual(
            total_row,
            ['', 0.0, 3.0, '0.00%', 0.0, 2.0, '0.00%', 8.0, 52.0, '15.38%', 0.0, 6.0, '0.00%', 0.0, 42.0,
             '0.00%', 3.0, 12.0, '25.00%', 0.0, 5.0, '0.00%', 0.0, 100.0, '0.00%']
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
            ['', 'CU', ' ', ' ', 'Collier', ' ', ' ', 'DIU', ' ', ' ', 'Depo-Provera', ' ', ' ',
             'Jadelle', ' ', ' ', 'Microgynon/Lof.', ' ', ' ', 'Microlut/Ovrette', ' ', ' ',
             'Preservatif Feminin', ' ', ' ', 'Preservatif Masculin', ' ', ' ']
        )
        self.assertEqual(
            rows,
            [['DEBI TIQUET', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '10.00', 'html': '10.00'},
              '0.00%', {'sort_key': '1.00', 'html': '1.00'}, {'sort_key': '4.00', 'html': '4.00'},
              '25.00%', {'sort_key': '1.00', 'html': '1.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '100.00%', {'sort_key': '24.00', 'html': '24.00'}, {'sort_key': '70.00', 'html': '70.00'},
              '34.29%', {'sort_key': '4.00', 'html': '4.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '80.00%', {'sort_key': '11.00', 'html': '11.00'}, {'sort_key': '49.00', 'html': '49.00'},
              '22.45%', {'sort_key': '17.00', 'html': '17.00'}, {'sort_key': '32.00', 'html': '32.00'},
              '53.12%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '0.00%', {'sort_key': '66.00', 'html': '66.00'}, {'sort_key': '186.00', 'html': '186.00'},
              '35.48%'],
             ['DIENDER', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '4.00', 'html': '4.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '0.00%', {'sort_key': '1.00', 'html': '1.00'}, {'sort_key': '6.00', 'html': '6.00'},
              '16.67%', {'sort_key': '46.00', 'html': '46.00'}, {'sort_key': '173.00', 'html': '173.00'},
              '26.59%', {'sort_key': '1.00', 'html': '1.00'}, {'sort_key': '11.00', 'html': '11.00'},
              '9.09%', {'sort_key': '64.00', 'html': '64.00'}, {'sort_key': '119.00', 'html': '119.00'},
              '53.78%', {'sort_key': '8.00', 'html': '8.00'}, {'sort_key': '26.00', 'html': '26.00'},
              '30.77%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '10.00', 'html': '10.00'},
              '0.00%', {'sort_key': '21.00', 'html': '21.00'}, {'sort_key': '47.00', 'html': '47.00'},
              '44.68%'],
             ['DIOGO', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '10.00', 'html': '10.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '0.00%', {'sort_key': '3.00', 'html': '3.00'}, {'sort_key': '2.00', 'html': '2.00'},
              '150.00%', {'sort_key': '182.00', 'html': '182.00'},
              {'sort_key': '242.00', 'html': '242.00'}, '75.21%', {'sort_key': '3.00', 'html': '3.00'},
              {'sort_key': '37.00', 'html': '37.00'}, '8.11%', {'sort_key': '89.00', 'html': '89.00'},
              {'sort_key': '202.00', 'html': '202.00'}, '44.06%', {'sort_key': '15.00', 'html': '15.00'},
              {'sort_key': '63.00', 'html': '63.00'}, '23.81%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '20.00', 'html': '20.00'}, '0.00%', {'sort_key': '10.00', 'html': '10.00'},
              {'sort_key': '98.00', 'html': '98.00'}, '10.20%'],
             ['GRAND THIES', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '24.00', 'html': '24.00'},
              '20.83%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '4.00', 'html': '4.00'},
              '0.00%', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '4.00', 'html': '4.00'},
              '125.00%', {'sort_key': '117.00', 'html': '117.00'},
              {'sort_key': '202.00', 'html': '202.00'}, '57.92%', {'sort_key': '5.00', 'html': '5.00'},
              {'sort_key': '14.00', 'html': '14.00'}, '35.71%', {'sort_key': '173.00', 'html': '173.00'},
              {'sort_key': '267.00', 'html': '267.00'}, '64.79%', {'sort_key': '57.00', 'html': '57.00'},
              {'sort_key': '38.00', 'html': '38.00'}, '150.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '10.00', 'html': '10.00'}, '0.00%', {'sort_key': '70.00', 'html': '70.00'},
              {'sort_key': '100.00', 'html': '100.00'}, '70.00%'],
             ['GUELOR WOLOF', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '4.00', 'html': '4.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '4.00', 'html': '4.00'},
              '0.00%', {'sort_key': '10.00', 'html': '10.00'}, {'sort_key': '62.00', 'html': '62.00'},
              '16.13%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '8.00', 'html': '8.00'},
              '0.00%', {'sort_key': '3.00', 'html': '3.00'}, {'sort_key': '66.00', 'html': '66.00'},
              '4.55%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '70.00', 'html': '70.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '60.00', 'html': '60.00'},
              '0.00%'],
             ['LERANE COLY', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '3.00', 'html': '3.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '2.00', 'html': '2.00'},
              '0.00%', {'sort_key': '8.00', 'html': '8.00'}, {'sort_key': '52.00', 'html': '52.00'},
              '15.38%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '6.00', 'html': '6.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '42.00', 'html': '42.00'},
              '0.00%', {'sort_key': '3.00', 'html': '3.00'}, {'sort_key': '12.00', 'html': '12.00'},
              '25.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '100.00', 'html': '100.00'},
              '0.00%'],
             ['MBANE DAGANA', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.00%', {'sort_key': '94.00', 'html': '94.00'}, {'sort_key': '267.00', 'html': '267.00'},
              '35.21%', {'sort_key': '3.00', 'html': '3.00'}, {'sort_key': '114.00', 'html': '114.00'},
              '2.63%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.00%'],
             ['NDIAWAR RICHARD TOLL', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '4.00', 'html': '4.00'}, '0.00%',
              {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '3.00', 'html': '3.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '5.00', 'html': '5.00'}, '0.00%',
              {'sort_key': '58.00', 'html': '58.00'}, {'sort_key': '29.00', 'html': '29.00'},
              '200.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '5.00', 'html': '5.00'}, '0.00%',
              {'sort_key': '116.00', 'html': '116.00'}, {'sort_key': '65.00', 'html': '65.00'},
              '178.46%', {'sort_key': '3.00', 'html': '3.00'},
              {'sort_key': '57.00', 'html': '57.00'}, '5.26%',
              {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '10.00', 'html': '10.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '100.00', 'html': '100.00'}, '0.00%'],
             ['NIANGUE DIAW', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '0.00%', {'sort_key': '1.00', 'html': '1.00'}, {'sort_key': '2.00', 'html': '2.00'},
              '50.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '11.00', 'html': '11.00'},
              '0.00%', {'sort_key': '69.00', 'html': '69.00'}, {'sort_key': '77.00', 'html': '77.00'},
              '89.61%', {'sort_key': '2.00', 'html': '2.00'}, {'sort_key': '21.00', 'html': '21.00'},
              '9.52%', {'sort_key': '48.00', 'html': '48.00'}, {'sort_key': '127.00', 'html': '127.00'},
              '37.80%', {'sort_key': '9.00', 'html': '9.00'}, {'sort_key': '65.00', 'html': '65.00'},
              '13.85%', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '16.00', 'html': '16.00'},
              '31.25%', {'sort_key': '32.00', 'html': '32.00'}, {'sort_key': '106.00', 'html': '106.00'},
              '30.19%'],
             ['PS CAMP MILITAIRE', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '5.00', 'html': '5.00'}, '0.00%',
              {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '4.00', 'html': '4.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '8.00', 'html': '8.00'}, '0.00%',
              {'sort_key': '4.00', 'html': '4.00'}, {'sort_key': '117.00', 'html': '117.00'},
              '3.42%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '9.00', 'html': '9.00'}, '0.00%',
              {'sort_key': '100.00', 'html': '100.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '10000.00%', {'sort_key': '3.00', 'html': '3.00'},
              {'sort_key': '158.00', 'html': '158.00'}, '1.90%',
              {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '10.00', 'html': '10.00'},
              '0.00%', {'sort_key': '234.00', 'html': '234.00'},
              {'sort_key': '546.00', 'html': '546.00'}, '42.86%'],
             ['PS DE DOUMGA OURO ALPHA', {'sort_key': '1.00', 'html': '1.00'},
              {'sort_key': '4.00', 'html': '4.00'}, '25.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '2.00', 'html': '2.00'}, '0.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '2.00', 'html': '2.00'}, '0.00%', {'sort_key': '5.00', 'html': '5.00'},
              {'sort_key': '83.00', 'html': '83.00'}, '6.02%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '5.00', 'html': '5.00'}, '0.00%', {'sort_key': '30.00', 'html': '30.00'},
              {'sort_key': '90.00', 'html': '90.00'}, '33.33%', {'sort_key': '12.00', 'html': '12.00'},
              {'sort_key': '18.00', 'html': '18.00'}, '66.67%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '10.00', 'html': '10.00'}, '0.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '100.00', 'html': '100.00'}, '0.00%'],
             ['PS DE KOBILO', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '4.00', 'html': '4.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '2.00', 'html': '2.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '2.00', 'html': '2.00'},
              '0.00%', {'sort_key': '9.00', 'html': '9.00'}, {'sort_key': '32.00', 'html': '32.00'},
              '28.12%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '0.00%', {'sort_key': '19.00', 'html': '19.00'}, {'sort_key': '9.00', 'html': '9.00'},
              '211.11%', {'sort_key': '9.00', 'html': '9.00'}, {'sort_key': '26.00', 'html': '26.00'},
              '34.62%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '10.00', 'html': '10.00'},
              '0.00%', {'sort_key': '22.00', 'html': '22.00'}, {'sort_key': '74.00', 'html': '74.00'},
              '29.73%'],
             ['PS DIOKOUL WAGUE', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '7.00', 'html': '7.00'}, '0.00%',
              {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '5.00', 'html': '5.00'}, '0.00%',
              {'sort_key': '28.00', 'html': '28.00'}, {'sort_key': '80.00', 'html': '80.00'},
              '35.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '15.00', 'html': '15.00'}, '0.00%',
              {'sort_key': '33.00', 'html': '33.00'},
              {'sort_key': '130.00', 'html': '130.00'}, '25.38%',
              {'sort_key': '21.00', 'html': '21.00'}, {'sort_key': '33.00', 'html': '33.00'},
              '63.64%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '5.00', 'html': '5.00'}, '0.00%',
              {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '84.00', 'html': '84.00'},
              '0.00%'],
             ['PS NGOR', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '4.00', 'html': '4.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '0.00%', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '3.00', 'html': '3.00'},
              '0.00%', {'sort_key': '100.00', 'html': '100.00'}, {'sort_key': '318.00', 'html': '318.00'},
              '31.45%', {'sort_key': '6.00', 'html': '6.00'}, {'sort_key': '28.00', 'html': '28.00'},
              '21.43%', {'sort_key': '179.00', 'html': '179.00'},
              {'sort_key': '345.00', 'html': '345.00'}, '51.88%', {'sort_key': '13.00', 'html': '13.00'},
              {'sort_key': '96.00', 'html': '96.00'}, '13.54%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '10.00', 'html': '10.00'}, '0.00%', {'sort_key': '6.00', 'html': '6.00'},
              {'sort_key': '144.00', 'html': '144.00'}, '4.17%'],
             ['PS PLLES ASS. UNITE 12', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '8.00', 'html': '8.00'}, '0.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '4.00', 'html': '4.00'}, '0.00%', {'sort_key': '13.00', 'html': '13.00'},
              {'sort_key': '1.00', 'html': '1.00'}, '1300.00%', {'sort_key': '139.00', 'html': '139.00'},
              {'sort_key': '433.00', 'html': '433.00'}, '32.10%', {'sort_key': '16.00', 'html': '16.00'},
              {'sort_key': '17.00', 'html': '17.00'}, '94.12%', {'sort_key': '215.00', 'html': '215.00'},
              {'sort_key': '403.00', 'html': '403.00'}, '53.35%', {'sort_key': '29.00', 'html': '29.00'},
              {'sort_key': '171.00', 'html': '171.00'}, '16.96%', {'sort_key': '10.00', 'html': '10.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '1000.00%', {'sort_key': '0.00', 'html': '0.00'},
              {'sort_key': '211.00', 'html': '211.00'}, '0.00%']],
        )
        self.assertEqual(
            total_row,
            ['', 6.0, 97.0, '6.19%', 2.0, 49.0, '4.08%', 23.0, 56.0, '41.07%', 799.0, 1970.0, '40.56%', 37.0,
             186.0, '19.89%', 1174.0, 2181.0, '53.83%', 202.0, 979.0, '20.63%', 15.0, 126.0, '11.90%', 461.0,
             1956.0, '23.57%']
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
            ['', 'CU', ' ', ' ', 'DIU', ' ', ' ', 'Depo-Provera', ' ', ' ', 'Jadelle', ' ', ' ',
             'Microgynon/Lof.', ' ', ' ', 'Microlut/Ovrette', ' ', ' ', 'Preservatif Feminin', ' ', ' ',
             'Preservatif Masculin', ' ', ' ']
        )
        self.assertEqual(
            rows,
            [['PASSY', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '5.000', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '5.000', {'sort_key': '77.00', 'html': '77.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '15.400', {'sort_key': '11.00', 'html': '11.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '11.000', {'sort_key': '42.00', 'html': '42.00'}, {'sort_key': '3.00', 'html': '3.00'},
              '14.000', {'sort_key': '30.00', 'html': '30.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '30.000', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '5.000', {'sort_key': '100.00', 'html': '100.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '100.000']],
        )
        self.assertEqual(
            total_row,
            ['', 5.0, 1.0, '5.000', 5.0, 1.0, '5.000', 77.0, 5.0, '15.400', 11.0, 1.0, '11.000', 42.0, 3.0,
             '14.000', 30.0, 1.0, '30.000', 5.0, 1.0, '5.000', 100.0, 1.0, '100.000']
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
            ['', 'CU', ' ', ' ', 'Collier', ' ', ' ', 'DIU', ' ', ' ', 'Depo-Provera', ' ', ' ',
             'Jadelle', ' ', ' ', 'Microgynon/Lof.', ' ', ' ', 'Microlut/Ovrette', ' ', ' ',
             'Preservatif Feminin', ' ', ' ', 'Preservatif Masculin', ' ', ' ']
        )
        self.assertEqual(
            rows,
            [['DEBI TIQUET', {'sort_key': '10.00', 'html': '10.00'}, {'sort_key': '9.00', 'html': '9.00'},
              '1.111', {'sort_key': '4.00', 'html': '4.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '4.000', {'sort_key': '1.00', 'html': '1.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '1.000', {'sort_key': '70.00', 'html': '70.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '70.000', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '5.000', {'sort_key': '49.00', 'html': '49.00'}, {'sort_key': '26.00', 'html': '26.00'},
              '1.885', {'sort_key': '32.00', 'html': '32.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '32.000', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '3.00', 'html': '3.00'},
              '1.667', {'sort_key': '186.00', 'html': '186.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '186.000'],
             ['DIENDER', {'sort_key': '4.00', 'html': '4.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '4.000', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '5.000', {'sort_key': '6.00', 'html': '6.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '6.000', {'sort_key': '173.00', 'html': '173.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '173.000', {'sort_key': '11.00', 'html': '11.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '11.000', {'sort_key': '179.00', 'html': '179.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '179.000', {'sort_key': '26.00', 'html': '26.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '26.000', {'sort_key': '10.00', 'html': '10.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '10.000', {'sort_key': '147.00', 'html': '147.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '147.000'],
             ['DIOGO', {'sort_key': '10.00', 'html': '10.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '10.000', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '5.000', {'sort_key': '8.00', 'html': '8.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '8.000', {'sort_key': '542.00', 'html': '542.00'}, {'sort_key': '4.00', 'html': '4.00'},
              '135.500', {'sort_key': '37.00', 'html': '37.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '37.000', {'sort_key': '262.00', 'html': '262.00'}, {'sort_key': '2.00', 'html': '2.00'},
              '131.000', {'sort_key': '63.00', 'html': '63.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '63.000', {'sort_key': '20.00', 'html': '20.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '20.000', {'sort_key': '98.00', 'html': '98.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '98.000'],
             ['GRAND THIES', {'sort_key': '24.00', 'html': '24.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '24.000', {'sort_key': '4.00', 'html': '4.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '4.000', {'sort_key': '14.00', 'html': '14.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '14.000', {'sort_key': '352.00', 'html': '352.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '352.000', {'sort_key': '14.00', 'html': '14.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '14.000', {'sort_key': '507.00', 'html': '507.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '507.000', {'sort_key': '158.00', 'html': '158.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '158.000', {'sort_key': '10.00', 'html': '10.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '10.000', {'sort_key': '200.00', 'html': '200.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '200.000'],
             ['GUELOR WOLOF', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '5.000', {'sort_key': '4.00', 'html': '4.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '4.000', {'sort_key': '4.00', 'html': '4.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '4.000', {'sort_key': '62.00', 'html': '62.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '62.000', {'sort_key': '8.00', 'html': '8.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '8.000', {'sort_key': '66.00', 'html': '66.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '66.000', {'sort_key': '70.00', 'html': '70.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '70.000', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '5.000', {'sort_key': '60.00', 'html': '60.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '60.000'],
             ['LERANE COLY', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '5.000', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.000', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '5.000', {'sort_key': '77.00', 'html': '77.00'}, {'sort_key': '5.00', 'html': '5.00'},
              '15.400', {'sort_key': '11.00', 'html': '11.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '11.000', {'sort_key': '42.00', 'html': '42.00'}, {'sort_key': '3.00', 'html': '3.00'},
              '14.000', {'sort_key': '30.00', 'html': '30.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '30.000', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '5.000', {'sort_key': '100.00', 'html': '100.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '100.000'],
             ['MBANE DAGANA', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.000', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.000', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.000', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.000', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.000', {'sort_key': '267.00', 'html': '267.00'}, {'sort_key': '89.00', 'html': '89.00'},
              '3.000', {'sort_key': '114.00', 'html': '114.00'}, {'sort_key': '33.00', 'html': '33.00'},
              '3.455', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.000', {'sort_key': '0.00', 'html': '0.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '0.000'],
             ['NDIAWAR RICHARD TOLL', {'sort_key': '4.00', 'html': '4.00'},
              {'sort_key': '86.00', 'html': '86.00'}, '0.047',
              {'sort_key': '3.00', 'html': '3.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '3.000', {'sort_key': '5.00', 'html': '5.00'},
              {'sort_key': '1.00', 'html': '1.00'}, '5.000',
              {'sort_key': '29.00', 'html': '29.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '29.000', {'sort_key': '5.00', 'html': '5.00'},
              {'sort_key': '1.00', 'html': '1.00'}, '5.000',
              {'sort_key': '65.00', 'html': '65.00'}, {'sort_key': '36.00', 'html': '36.00'},
              '1.806', {'sort_key': '57.00', 'html': '57.00'},
              {'sort_key': '1.00', 'html': '1.00'}, '57.000',
              {'sort_key': '10.00', 'html': '10.00'}, {'sort_key': '1.00', 'html': '1.00'},
              '10.000', {'sort_key': '100.00', 'html': '100.00'},
              {'sort_key': '1.00', 'html': '1.00'}, '100.000'],
             ['NIANGUE DIAW', {'sort_key': '5.00', 'html': '5.00'},
              {'sort_key': '45.00', 'html': '45.00'}, '0.111', {'sort_key': '3.00', 'html': '3.00'},
              {'sort_key': '1.00', 'html': '1.00'}, '3.000', {'sort_key': '11.00', 'html': '11.00'},
              {'sort_key': '1.00', 'html': '1.00'}, '11.000', {'sort_key': '177.00', 'html': '177.00'},
              {'sort_key': '1.00', 'html': '1.00'}, '177.000', {'sort_key': '24.00', 'html': '24.00'},
              {'sort_key': '1.00', 'html': '1.00'}, '24.000', {'sort_key': '135.00', 'html': '135.00'},
              {'sort_key': '55.00', 'html': '55.00'}, '2.455', {'sort_key': '83.00', 'html': '83.00'},
              {'sort_key': '8.00', 'html': '8.00'}, '10.375', {'sort_key': '16.00', 'html': '16.00'},
              {'sort_key': '27.00', 'html': '27.00'}, '0.593', {'sort_key': '106.00', 'html': '106.00'},
              {'sort_key': '1.00', 'html': '1.00'}, '106.000'],
             ['PS CAMP MILITAIRE', {'sort_key': '5.00', 'html': '5.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '5.000', {'sort_key': '4.00', 'html': '4.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '4.000', {'sort_key': '8.00', 'html': '8.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '8.000', {'sort_key': '117.00', 'html': '117.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '117.000', {'sort_key': '9.00', 'html': '9.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '9.000', {'sort_key': '100.00', 'html': '100.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '100.000', {'sort_key': '158.00', 'html': '158.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '158.000', {'sort_key': '10.00', 'html': '10.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '10.000', {'sort_key': '546.00', 'html': '546.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '546.000'],
             ['PS DE DOUMGA OURO ALPHA', {'sort_key': '4.00', 'html': '4.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '4.000', {'sort_key': '2.00', 'html': '2.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '2.000', {'sort_key': '2.00', 'html': '2.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '2.000', {'sort_key': '83.00', 'html': '83.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '83.000', {'sort_key': '5.00', 'html': '5.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '5.000', {'sort_key': '90.00', 'html': '90.00'},
              {'sort_key': '1.00', 'html': '1.00'}, '90.000', {'sort_key': '36.00', 'html': '36.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '36.000', {'sort_key': '10.00', 'html': '10.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '10.000', {'sort_key': '100.00', 'html': '100.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '100.000'],
             ['PS DE KOBILO', {'sort_key': '4.00', 'html': '4.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '4.000', {'sort_key': '2.00', 'html': '2.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '2.000', {'sort_key': '2.00', 'html': '2.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '2.000', {'sort_key': '32.00', 'html': '32.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '32.000', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '5.000', {'sort_key': '57.00', 'html': '57.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '57.000', {'sort_key': '26.00', 'html': '26.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '26.000', {'sort_key': '10.00', 'html': '10.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '10.000', {'sort_key': '74.00', 'html': '74.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '74.000'],
             ['PS DIOKOUL WAGUE', {'sort_key': '7.00', 'html': '7.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '7.000',
              {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '5.000', {'sort_key': '5.00', 'html': '5.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '5.000',
              {'sort_key': '180.00', 'html': '180.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '180.000', {'sort_key': '15.00', 'html': '15.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '15.000',
              {'sort_key': '130.00', 'html': '130.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '130.000', {'sort_key': '63.00', 'html': '63.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '63.000',
              {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '5.000', {'sort_key': '84.00', 'html': '84.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '84.000'],
             ['PS NGOR', {'sort_key': '4.00', 'html': '4.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '4.000', {'sort_key': '5.00', 'html': '5.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '5.000', {'sort_key': '3.00', 'html': '3.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '3.000', {'sort_key': '418.00', 'html': '418.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '418.000', {'sort_key': '28.00', 'html': '28.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '28.000', {'sort_key': '545.00', 'html': '545.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '545.000', {'sort_key': '96.00', 'html': '96.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '96.000', {'sort_key': '10.00', 'html': '10.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '10.000', {'sort_key': '144.00', 'html': '144.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '144.000'],
             ['PS PLLES ASS. UNITE 12', {'sort_key': '8.00', 'html': '8.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '8.000',
              {'sort_key': '4.00', 'html': '4.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '4.000', {'sort_key': '31.00', 'html': '31.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '31.000',
              {'sort_key': '433.00', 'html': '433.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '433.000', {'sort_key': '37.00', 'html': '37.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '37.000',
              {'sort_key': '503.00', 'html': '503.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '503.000', {'sort_key': '171.00', 'html': '171.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '171.000',
              {'sort_key': '10.00', 'html': '10.00'}, {'sort_key': '0.00', 'html': '0.00'},
              '10.000', {'sort_key': '211.00', 'html': '211.00'},
              {'sort_key': '0.00', 'html': '0.00'}, '211.000']]
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
            ['District', 'Collier', 'CU', 'Depo-Provera', 'DIU', 'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [['FATICK', 0, 0, 0, 0, 0, 0, 0, 0, 0], ['NIAKHAR', 0, 0, 0, 0, 0, 0, 0, 0, 0],
             ['PASSY', 0, 0, 0, 0, 0, 0, 0, 0, 0]]
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
            ['PPS', 'Collier', 'CU', 'Depo-Provera', 'DIU', 'Jadelle', 'Microgynon/Lof.',
             'Microlut/Ovrette', 'Preservatif Feminin', 'Preservatif Masculin']
        )
        self.assertEqual(
            rows,
            [['DJILOR SALOUM', 0, 0, 0, 0, 0, 0, 0, 0, 0],
             ['LERANE COLY', 0, 0, 0, 0, 0, 0, 0, 0, 0],
             ['MBELLONGOUTTE', 0, 0, 0, 0, 0, 0, 0, 0, 0],
             ['NDAIYE NDIAYE OUOLOF', 0, 0, 0, 0, 0, 0, 0, 0, 0],
             ['NDIONGOLOR', 0, 0, 0, 0, 0, 0, 0, 0, 0],
             ['NIASSENE', 0, 0, 0, 0, 0, 0, 0, 0, 0],
             ['PATAR SINE', 0, 0, 0, 0, 0, 0, 0, 0, 0], ['PEULGHA', 0, 0, 0, 0, 0, 0, 0, 0, 0],
             ['SENGHOR', 0, 0, 0, 0, 0, 0, 0, 0, 0]],
        )
        self.assertEqual(
            total_row,
            ['Taux rupture', '(0/9) 0.00%', '(0/9) 0.00%', '(0/9) 0.00%', '(0/9) 0.00%', '(0/9) 0.00%',
             '(0/9) 0.00%', '(0/9) 0.00%', '(0/9) 0.00%', '(0/9) 0.00%']
        )

    def test_duree_data_report(self):
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

    def test_duree_data_report_countrywide(self):
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

    def test_recouvrement_des_couts_report(self):
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

    def test_recouvrement_des_couts_report_countrywide(self):
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
