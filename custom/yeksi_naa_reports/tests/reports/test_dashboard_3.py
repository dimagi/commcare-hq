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
                ['ACETATE DE MEDROXY PROGESTERONE 104MG/0.65ML INJ. (SAYANA PRESS)', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 '100.00%'],
                ['ACETATE DE MEDROXY PROGESTERONE 150MG/ML+S A B KIT (1+1) (DEPO-PROVERA)', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 '150.00%'], ['ACT ADULTE', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                              'pas de donn\xe9es', 'pas de donn\xe9es', '100.00%'],
                ['ACT PETIT ENFANT', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', '100.00%'],
                ['ALBENDAZOL 4% SB.', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', '100.00%'],
                ['DISPOSITIF INTRA UTERIN (TCU 380 A) - DIU', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', '1462.40%'],
                ['EFAVIRENZ 600MG CP.', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', '80.77%'],
                ['LAMIVUDINE+NEVIRAPINE+ZIDOVUDINE (30+50+60)MG CP.', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', '100.00%'],
                ['LEVONORGESTREL+ETHYNILESTRADIOL+FER (0.15+0.03+75)MG (MICROGYNON)', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 '222.22%'],
                ['NEVIRAPINE 200MG CP.', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', '93.30%'],
                ['PARACETAMOL 500MG CP.', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
                ['Produit 1', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
                ['Produit 10', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', '87.10%', '96.30%'],
                ['Produit 12', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es'],
                ['Produit 14', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', '90.00%'],
                ['Produit 15', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', '100.00%'],
                ['Produit 2', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', '100.00%'],
                ['Produit A', '97.63%', '94.86%', '100.00%', '100.00%', '95.24%', '100.00%'],
                ['Produit B', '98.28%', '98.94%', '98.60%', '142.86%', '166.67%', '114.29%'],
                ['Produit C', '93.88%', '93.28%', 'pas de donn\xe9es', '111.11%', 'pas de donn\xe9es',
                 'pas de donn\xe9es'],
                ['RIFAMPICINE+ISONIAZIDE (150+75)MG CP.', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', '101.21%'],
                ['RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE (60+30+150)MG CP. DISPER', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 '100.00%'],
                ['RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE+ETHAMBUTOL (150+75+400+2', 'pas de donn\xe9es',
                 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es',
                 '100.00%'], ['TEST RAPIDE HIV 1/2 (SD BIOLINE)', 'pas de donn\xe9es', 'pas de donn\xe9es',
                              'pas de donn\xe9es', 'pas de donn\xe9es', 'pas de donn\xe9es', '100.00%']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Total (CFA)', '96.89%', '95.77%', '99.02%', '119.05%', '114.47%', '188.23%']
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
                ['ACETATE DE MEDROXY PROGESTERONE 104MG/0.65ML INJ. (SAYANA PRESS)', '0.00', '0.00', '0.00',
                 '0.00', '0.00', '0.00'],
                ['ACETATE DE MEDROXY PROGESTERONE 150MG/ML+S A B KIT (1+1) (DEPO-PROVERA)', '0.00', '0.00',
                 '0.00', '0.00', '0.00', '0.00'],
                ['ACT ADULTE', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['ACT PETIT ENFANT', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['ALBENDAZOL 4% SB.', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['DISPOSITIF INTRA UTERIN (TCU 380 A) - DIU', '0.00', '0.00', '0.00', '0.00', '0.00',
                 '0.00'], ['EFAVIRENZ 600MG CP.', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['LAMIVUDINE+NEVIRAPINE+ZIDOVUDINE (30+50+60)MG CP.', '0.00', '0.00', '0.00', '0.00', '0.00',
                 '0.00'],
                ['LEVONORGESTREL+ETHYNILESTRADIOL+FER (0.15+0.03+75)MG (MICROGYNON)', '0.00', '0.00', '0.00',
                 '0.00', '0.00', '0.00'],
                ['NEVIRAPINE 200MG CP.', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['PARACETAMOL 500MG CP.', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit 1', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit 10', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit 12', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit 14', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit 15', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit 2', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit A', '442500.00', '717500.00', '412500.00', '150000.00', '437500.00', '150000.00'],
                ['Produit B', '336000.00', '558000.00', '334500.00', '157500.00', '453000.00', '127500.00'],
                ['Produit C', '198000.00', '386400.00', '0.00', '120000.00', '0.00', '0.00'],
                ['RIFAMPICINE+ISONIAZIDE (150+75)MG CP.', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE (60+30+150)MG CP. DISPER', '0.00', '0.00', '0.00',
                 '0.00', '0.00', '0.00'],
                ['RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE+ETHAMBUTOL (150+75+400+2', '0.00', '0.00', '0.00',
                 '0.00', '0.00', '0.00'],
                ['TEST RAPIDE HIV 1/2 (SD BIOLINE)', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            [
                'Total (CFA)', '976500.00', '1661900.00', '747000.00', '427500.00', '890500.00',
                '277500.00'
            ]
        )
