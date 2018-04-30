# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from mock.mock import MagicMock

from custom.yeksi_naa_reports.tests.utils import YeksiTestCase
from custom.yeksi_naa_reports.reports import Dashboard3Report


class TestDashboard3(YeksiTestCase):

    def test_satisfaction_rate_after_delivery_data_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'program': '%%',
            'month_start': '10',
            'year_start': '2017',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard3_report = Dashboard3Report(request=mock, domain='test-pna')

        satisfaction_rate_after_delivery_data_report = \
            dashboard3_report.report_context['reports'][0]['report_table']
        headers = satisfaction_rate_after_delivery_data_report['headers'].as_export_table[0]
        rows = satisfaction_rate_after_delivery_data_report['rows']
        total_row = satisfaction_rate_after_delivery_data_report['total_row']

        self.assertEqual(
            headers,
            ['Produit', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018']
        )
        self.assertEqual(
            rows,
            sorted([
                [u'ACETATE DE MEDROXY PROGESTERONE 104MG/0.65ML INJ. (SAYANA PRESS)', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'100.00%'],
                [u'ACETATE DE MEDROXY PROGESTERONE 150MG/ML+S A B KIT (1+1) (DEPO-PROVERA)', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'150.00%'], [u'ACT ADULTE', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                               u'pas de donn\xe9es', u'pas de donn\xe9es', u'100.00%'],
                [u'ACT PETIT ENFANT', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'100.00%'],
                [u'ALBENDAZOL 4% SB.', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'100.00%'],
                [u'DISPOSITIF INTRA UTERIN (TCU 380 A) - DIU', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es', u'1462.40%'],
                [u'EFAVIRENZ 600MG CP.', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'80.77%'],
                [u'LAMIVUDINE+NEVIRAPINE+ZIDOVUDINE (30+50+60)MG CP.', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es', u'100.00%'],
                [u'LEVONORGESTREL+ETHYNILESTRADIOL+FER (0.15+0.03+75)MG (MICROGYNON)', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'222.22%'],
                [u'NEVIRAPINE 200MG CP.', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'93.30%'],
                [u'PARACETAMOL 500MG CP.', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es'],
                [u'Produit 1', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es'],
                [u'Produit 10', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'87.10%', u'96.30%'],
                [u'Produit 12', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es'],
                [u'Produit 14', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'90.00%'],
                [u'Produit 15', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'100.00%'],
                [u'Produit 2', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'100.00%'],
                [u'Produit A', u'97.63%', u'94.86%', u'100.00%', u'100.00%', u'95.24%', u'100.00%'],
                [u'Produit B', u'98.28%', u'98.94%', u'98.60%', u'142.86%', u'166.67%', u'114.29%'],
                [u'Produit C', u'93.88%', u'93.28%', u'pas de donn\xe9es', u'111.11%', u'pas de donn\xe9es',
                 u'pas de donn\xe9es'],
                [u'RIFAMPICINE+ISONIAZIDE (150+75)MG CP.', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es', u'101.21%'],
                [u'RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE (60+30+150)MG CP. DISPER', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'100.00%'],
                [u'RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE+ETHAMBUTOL (150+75+400+2', u'pas de donn\xe9es',
                 u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es',
                 u'100.00%'], [u'TEST RAPIDE HIV 1/2 (SD BIOLINE)', u'pas de donn\xe9es', u'pas de donn\xe9es',
                               u'pas de donn\xe9es', u'pas de donn\xe9es', u'pas de donn\xe9es', u'100.00%']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [u'Total (CFA)', u'96.89%', u'95.77%', u'99.02%', u'119.05%', u'114.47%', u'188.23%']
        )

    def test_valuation_of_pna_stock_per_product_data_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'program': '%%',
            'month_start': '10',
            'year_start': '2017',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard3_report = Dashboard3Report(request=mock, domain='test-pna')

        valuation_of_pna_stock_per_product_data_report = \
            dashboard3_report.report_context['reports'][1]['report_table']
        headers = valuation_of_pna_stock_per_product_data_report['headers'].as_export_table[0]
        rows = valuation_of_pna_stock_per_product_data_report['rows']
        total_row = valuation_of_pna_stock_per_product_data_report['total_row']

        self.assertEqual(
            headers,
            ['Produit', 'Octobre 2017', 'Novembre 2017', 'Décembre 2017', 'Janvier 2018',
             'Février 2018', 'Mars 2018']
        )
        self.assertItemsEqual(
            rows,
            sorted([
                [u'ACETATE DE MEDROXY PROGESTERONE 104MG/0.65ML INJ. (SAYANA PRESS)', u'0.00', u'0.00', u'0.00',
                 u'0.00', u'0.00', u'0.00'],
                [u'ACETATE DE MEDROXY PROGESTERONE 150MG/ML+S A B KIT (1+1) (DEPO-PROVERA)', u'0.00', u'0.00',
                 u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'ACT ADULTE', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'ACT PETIT ENFANT', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'ALBENDAZOL 4% SB.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'DISPOSITIF INTRA UTERIN (TCU 380 A) - DIU', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00',
                 u'0.00'], [u'EFAVIRENZ 600MG CP.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'LAMIVUDINE+NEVIRAPINE+ZIDOVUDINE (30+50+60)MG CP.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00',
                 u'0.00'],
                [u'LEVONORGESTREL+ETHYNILESTRADIOL+FER (0.15+0.03+75)MG (MICROGYNON)', u'0.00', u'0.00', u'0.00',
                 u'0.00', u'0.00', u'0.00'],
                [u'NEVIRAPINE 200MG CP.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'PARACETAMOL 500MG CP.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 1', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 10', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 12', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 14', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 15', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 2', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit A', u'442500.00', u'717500.00', u'412500.00', u'150000.00', u'437500.00', u'150000.00'],
                [u'Produit B', u'336000.00', u'558000.00', u'334500.00', u'157500.00', u'453000.00', u'127500.00'],
                [u'Produit C', u'198000.00', u'386400.00', u'0.00', u'120000.00', u'0.00', u'0.00'],
                [u'RIFAMPICINE+ISONIAZIDE (150+75)MG CP.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE (60+30+150)MG CP. DISPER', u'0.00', u'0.00', u'0.00',
                 u'0.00', u'0.00', u'0.00'],
                [u'RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE+ETHAMBUTOL (150+75+400+2', u'0.00', u'0.00', u'0.00',
                 u'0.00', u'0.00', u'0.00'],
                [u'TEST RAPIDE HIV 1/2 (SD BIOLINE)', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                u'Total (CFA)', u'976500.00', u'1661900.00', u'747000.00', u'427500.00', u'890500.00',
                u'277500.00'
            ]
        )
