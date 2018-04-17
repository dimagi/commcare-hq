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
            ['Product', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE+ETHAMBUTOL (150+75+400+2', 'no data entered',
                 'no data entered', 'no data entered', 'no data entered', 'no data entered', '100.00%'],
                ['NEVIRAPINE 200MG CP.', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '93.30%'],
                ['ACETATE DE MEDROXY PROGESTERONE 104MG/0.65ML INJ. (SAYANA PRESS)', 'no data entered',
                 'no data entered', 'no data entered', 'no data entered', 'no data entered', '100.00%'],
                ['ACT ADULTE', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '100.00%'],
                ['Produit A', '97.63%', '94.86%', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered'],
                ['Produit 10', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 '87.10%', '96.30%'],
                ['Produit 12', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['LAMIVUDINE+NEVIRAPINE+ZIDOVUDINE (30+50+60)MG CP.', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', 'no data entered', '100.00%'],
                ['DISPOSITIF INTRA UTERIN (TCU 380 A) - DIU', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', 'no data entered', '1462.40%'],
                ['PARACETAMOL 500MG CP.', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', 'no data entered'],
                ['EFAVIRENZ 600MG CP.', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '80.77%'],
                ['RIFAMPICINE+ISONIAZIDE (150+75)MG CP.', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', 'no data entered', '101.21%'],
                ['Produit 15', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '100.00%'],
                ['Test Product 1', '518.75%', '592.86%', '691.67%', '345.83%', '129.69%', '98.44%'],
                ['Produit 14', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '90.00%'],
                ['ACETATE DE MEDROXY PROGESTERONE 150MG/ML+S A B KIT (1+1) (DEPO-PROVERA)', 'no data entered',
                 'no data entered', 'no data entered', 'no data entered', 'no data entered', '150.00%'],
                ['Produit 2', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', '100.00%'],
                ['ACT PETIT ENFANT', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '100.00%'],
                ['Produit 1', 'no data entered', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered'],
                ['ALBENDAZOL 4% SB.', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '100.00%'],
                ['LEVONORGESTREL+ETHYNILESTRADIOL+FER (0.15+0.03+75)MG (MICROGYNON)', 'no data entered',
                 'no data entered', 'no data entered', 'no data entered', 'no data entered', '222.22%'],
                ['Produit C', '93.88%', '93.28%', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered'],
                ['RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE (60+30+150)MG CP. DISPER', 'no data entered',
                 'no data entered', 'no data entered', 'no data entered', 'no data entered', '100.00%'],
                ['TEST RAPIDE HIV 1/2 (SD BIOLINE)', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered', 'no data entered', '100.00%'],
                ['Produit B', '98.28%', '98.94%', 'no data entered', 'no data entered', 'no data entered',
                 'no data entered']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Total (CFA)', '104.01%', '104.28%', '691.67%', '345.83%', '99.54%', '188.90%']
        )

    def test_valuation_of_pna_stock_per_product_data_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
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
            ['Product', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertItemsEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE+ETHAMBUTOL (150+75+400+2', '0.00', '0.00', '0.00',
                 '0.00', '0.00', '0.00'],
                ['NEVIRAPINE 200MG CP.', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['ACETATE DE MEDROXY PROGESTERONE 104MG/0.65ML INJ. (SAYANA PRESS)', '0.00', '0.00', '0.00',
                 '0.00', '0.00', '0.00'], ['ACT ADULTE', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit A', '442500.00', '717500.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit 10', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit 12', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['LAMIVUDINE+NEVIRAPINE+ZIDOVUDINE (30+50+60)MG CP.', '0.00', '0.00', '0.00', '0.00', '0.00',
                 '0.00'],
                ['DISPOSITIF INTRA UTERIN (TCU 380 A) - DIU', '0.00', '0.00', '0.00', '0.00', '0.00',
                 '0.00'], ['PARACETAMOL 500MG CP.', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['EFAVIRENZ 600MG CP.', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['RIFAMPICINE+ISONIAZIDE (150+75)MG CP.', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit 15', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Test Product 1', '455000.00', '455000.00', '455000.00', '455000.00', '455000.00',
                 '455000.00'], ['Produit 14', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['ACETATE DE MEDROXY PROGESTERONE 150MG/ML+S A B KIT (1+1) (DEPO-PROVERA)', '0.00', '0.00',
                 '0.00', '0.00', '0.00', '0.00'],
                ['Produit 2', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['ACT PETIT ENFANT', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit 1', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['ALBENDAZOL 4% SB.', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['LEVONORGESTREL+ETHYNILESTRADIOL+FER (0.15+0.03+75)MG (MICROGYNON)', '0.00', '0.00', '0.00',
                 '0.00', '0.00', '0.00'],
                ['Produit C', '198000.00', '386400.00', '0.00', '0.00', '0.00', '0.00'],
                ['RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE (60+30+150)MG CP. DISPER', '0.00', '0.00', '0.00',
                 '0.00', '0.00', '0.00'],
                ['TEST RAPIDE HIV 1/2 (SD BIOLINE)', '0.00', '0.00', '0.00', '0.00', '0.00', '0.00'],
                ['Produit B', '336000.00', '558000.00', '0.00', '0.00', '0.00', '0.00']
            ], key=lambda x: x[0])
        )
        self.assertEqual(
            total_row,
            ['Total (CFA)', '1431500.00', '2116900.00', '455000.00', '455000.00', '455000.00', '455000.00']
        )
