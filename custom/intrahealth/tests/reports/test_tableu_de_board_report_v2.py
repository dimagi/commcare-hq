# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import datetime

from mock.mock import MagicMock

from custom.intrahealth.tests.utils import YeksiTestCase
from custom.intrahealth.reports import TableuDeBoardReport2
from dimagi.utils.dates import DateSpan
from datetime import datetime


class TestFicheConsommationReportV2(YeksiTestCase):

    def test_conventure_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2014-06-01',
            'enddate': '2014-07-31',
            'location_id': '1991b4dfe166335e342f28134b85fcac',
        }
        mock.datespan = DateSpan(datetime(2014, 6, 1), datetime(2014, 7, 31))

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
        mock.datespan = DateSpan(datetime(2014, 6, 1), datetime(2014, 7, 31))

        tableu_de_board_report2_report = TableuDeBoardReport2(request=mock, domain='test-pna')

        PPS_avec_donnees_report = tableu_de_board_report2_report.report_context['reports'][1]['report_table']
        headers = PPS_avec_donnees_report['headers'].as_export_table[0]
        rows = PPS_avec_donnees_report['rows']

        print(headers)
        print(rows)
        self.assertEqual(
            headers,
            [u'PPS', 'PPS Avec Donn\xe9es Soumises']
        )
        self.assertEqual(
            rows,
            [['NIAKHAR', 1], ['PASSY', 1], ['DIOFFIOR', 1], ['GOSSAS', 1], [None, 1], ['FOUNDIOUGNE', 1],
             ['SOKONE', 1], ['FATICK', 1]]

        )

    def test_products_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'startdate': '2016-05-28',
            'enddate': '2018-06-04',
            'location_id': '',
        }
        mock.datespan = DateSpan(datetime(2016, 5, 28), datetime(2018, 6, 4))

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
                ['Commandes', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2027, 0, 0, 0, 0, 200, 5100,
                 164600, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2468, 0, 14530, 0, 0, 0, 0, 0, 208280,
                 26640, 0, 0, 0, 0, 0, 0, 0, 0, 200, 351079, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 35800,
                 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['Raux', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2027, 0, 0, 0, 0, 200, 5100,
                 156735, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 565, 0, 12730, 0, 0, 0, 0, 0, 198317,
                 26640, 0, 0, 0, 0, 0, 0, 0, 0, 0, 351079, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 35800,
                 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                ['Taux', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%',
                 '100%', '0%', '0%', '0%', '0%', '100%', '100%', '105%', '0%', '0%', '0%', '0%', '0%',
                 '0%', '0%', '0%', '0%', '0%', '0%', '436%', '0%', '114%', '0%', '0%', '0%', '0%', '0%',
                 '105%', '100%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '20000%', '100%', '0%',
                 '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '100%', '0%', '0%', '0%', '0%',
                 '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%',
                 '0%']
            ]
        )
