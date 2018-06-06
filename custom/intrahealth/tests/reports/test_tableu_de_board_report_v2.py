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
            [['Ao\xfbt', 0, 0, 17, '1700.00%', 17, '100.00%']]
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

        self.assertEqual(
            headers,
            ['PPS', 'PPS Avec Donn\xe9es Soumises']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([['NIAKHAR', 1], ['PASSY', 1], ['DIOFFIOR', 1], ['GOSSAS', 1], ['FOUNDIOUGNE', 1],
                    ['SOKONE', 1], ['FATICK', 1]], key=lambda x: x[0])
        )

    def test_consommation_data_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2016-05-28',
            'enddate': '2018-06-04',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2016, 5, 28), datetime.datetime(2018, 6, 4))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        consommation_data_report = tableu_de_board_report2_report.report_context['reports'][3]['report_table']
        headers = consommation_data_report['headers'].as_export_table[0]
        rows = consommation_data_report['rows']

        self.assertEqual(
            headers,
            ['PPS', 'Consumption']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['NDIOLOFENE', 0], ['PS HLM FASS', 380], ['CS LIBERTE 6 EXTENTION', 89], ['P.S NDIMB', 146],
                ['PS MARSASSOUM SEDHIOU', 0], [u'PS MEDINA GOUNASS', 397], ['HOPITAL REGIONAL DE KOLDA', 793],
                ['DAROU MBITEYENE', 69], ['PS Sendou', 0], [u'MEDINA BAYE', 445], ['NAYOBE', 132], ['FASS', 171],
                ['BETENTY', 2149], ['TASSINERE', 442], ['PS DIAMAGUENE', 411], ['NDANGALMA', 160],
                ['PPS SANTHIABA ZIGUINCHOR', 0], ['GATE', 199], ['PS TANAFF GOUDOMP', 6365], ['SAMBA DIA', 1214],
                ['THIEPP  KEBEMER', 0], [u"N'GALLELE SAINT LOUIS", 353], ['CARITAS', 4247], ['PS YOUTOU', 0],
                [u'Thille Boubacar', 222], ['PPS ORKADIERE', 964], ['GANDIAYE', 800], ['PS WASSADOU', 43],
                [u'PS MAMPALAGO BIGNONA', 488], ['RAYON PRIVE SOKONE', 650], ['MEKHE LAMBAYE', 50],
                ['THILAGRAND', 570], ['BACOBOF', 482], ['SOBEME', 291], ['PS FASS', 208],
                ['HOP. MILITAIRE OUAKAM', 256], ['Wallalde', 193], ['PS HANN SUR MER', 133],
                ['PS TOUBA DIACK SAO', 503], ['EPS 1 KAFFRINE', 236]
            ], key=lambda x: x[0])
        )

    def test_products_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime.datetime(2014, 6, 1), datetime.datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        products_report = tableu_de_board_report2_report.report_context['reports'][1]['report_table']
        headers = products_report['headers'].as_export_table[0]
        rows = products_report['rows']
        self.assertEqual(
            headers,
            [
                'Quantity', 'ACT Adulte', 'ACT Grand Enfant', 'ACT Nourisson', 'ACT Petit Enfant',
                'ASAQ Adulte', 'ASAQ Grand Enfant', 'ASAQ Nourisson', 'ASAQ Petit Enfant', 'Amoxicillin 250mg',
                'Amoxicillin 250mg CP', 'Amoxicilline 250mg SP', 'Ampiciline 1G Amp',
                'Bo\xeete de s\xe9curit\xe9', 'CU', 'Calcium 100mg', 'Cefixime 100MG/5ML SUSP.BUV',
                'Ceftriaxone 1G', 'Chlorexedine', 'Collier', 'DIU', 'Depo-Provera', 'Dexamethasone 4mg',
                'Diazepam 10MG/2ML AMP. INJ.', 'Diluant BCG', 'Diluant Fi\xe8vre Jaune (VAA)',
                'Diluant Rougeole (RR)', 'EFAVIRENZ 600MG CP.', 'Epinephrine 1MG/1ML AMP. INJ.', 'Fer 0.68% SP',
                'Gentamicin 40mg/2ml', 'Gentamicin INJ 80mg/2ml', 'Hydrocortisone 100MG AMP. INJ.', 'IMPLANON',
                'ISONIAZIDE 100MG CP.', 'Jadelle', 'Kit de depistage Rapide du VIH B/30',
                'LAMIVUDINE 30 NEVIRAPINE 50 ZIDOVUDINE 60 MG CP.', 'Magnesium sulfate 500mg',
                'Mebendazole 100MG SP', 'Mebendazole 500MG CP.', 'Microgynon/Lof.', 'Microlut/Ovrette',
                'Misoprostol 200mcg', 'NEVIRAPINE 200MG CP', 'Nicardipine', 'Oxytocine 5 UI',
                'Paracetamol 120MG/5ML SP', 'Paracetamol 1G/100ML INJ.', 'Phytomenadione 10mg', 'Pneumo',
                'Preservatif Feminin', 'Preservatif Masculin', 'Product 7', 'RIFAMPICINE 150 ISONIAZIDE 75MG CP.',
                'RIFAMPICINE 60 ISONIAZIDE 30MG CP. DISPERSIBLE',
                'RIFAMPICINE150 ISONIAZIDE 75 PYRAZINAMIDE400 ETHAMBUTOL2',
                'RIFAMPICINE60 ISONIAZIDE30 PYRAZINAMIDE150MG CP.DISPER', 'Recto caps 200 mg', 'Recto caps 50 mg',
                'Rota', 'S.R.O. Faible osmolarite', 'STREPTOMYCINE 1G AMP. INJ.', 'Sayana Press',
                'Seringue Autobloquante 0,05 ml', 'Seringue Autobloquante 0,5 ml', 'Seringue de dilution 2 ML',
                'Seringue de dilution 5 ML (SD)', 'Sulfate de Magnesium 20 ml',
                'TENOFOVIR 300 LAMIVUDINE 300 EFAVIRENZ  600 MG CP.', 'TENOFOVIR 300 LAMIVUDINE 300MG CP.',
                'Test depistage rapide Palu', 'Tubercoline', 'Vaccin BCG', 'Vaccin DIPH - T\xe9tanique (Td)',
                'Vaccin Fi\xe8vre Jaune (VAA)', 'Vaccin H\xe9patite B', 'Vaccin Penta', 'Vaccin Rougeole (RR)',
                'Vaccin VPI', 'Vaccin VPO', 'ZIDOVUDINE 300 LAMIVUDINE 150MG CP', 'Zinc 20mg'
            ]
        )
        self.assertEqual(
            rows,
            [
                [
                    'Commandes', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1842, 0, 0, 0, 0, 217, 2194, 90675, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7510, 0, 0, 0, 0, 0, 113080, 7200, 0, 0, 0, 0, 0, 0, 0,
                    0, 4000, 48000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0
                ],
                [
                    'Raux', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1842, 0, 0, 0, 0, 217, 2194, 51308, 0, 0,
                    0,
                    0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 5810, 0, 0, 0, 0, 0, 59080, 7200, 0, 0, 0, 0, 0, 0, 0, 0, 4000,
                    48000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0
                ],
                [
                    'Taux', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%',
                    '0%',
                    '100%', '0%', '0%', '0%', '0%', '100%', '100%', '176%', '0%', '0%', '0%', '0%',
                    '0%',
                    '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '129%', '0%', '0%', '0%', '0%',
                    '0%',
                    '191%', '100%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '100%', '100%',
                    '0%',
                    '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%',
                    '0%',
                    '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%',
                    '0%',
                    '0%'
                ]
            ]
        )
