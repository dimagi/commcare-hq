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

        self.assertEqual(
            headers,
            ['Product', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE+ETHAMBUTOL (150+75+400+2', u'no data entered',
                 u'no data entered', u'no data entered', u'no data entered', u'no data entered', u'100.00%'],
                [u'NEVIRAPINE 200MG CP.', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'93.30%'],
                [u'ACETATE DE MEDROXY PROGESTERONE 104MG/0.65ML INJ. (SAYANA PRESS)', u'no data entered',
                 u'no data entered', u'no data entered', u'no data entered', u'no data entered', u'100.00%'],
                [u'ACT ADULTE', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'100.00%'],
                [u'Produit A', u'97.63%', u'94.86%', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered'],
                [u'Produit 10', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'87.10%', u'96.30%'],
                [u'Produit 12', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'LAMIVUDINE+NEVIRAPINE+ZIDOVUDINE (30+50+60)MG CP.', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'no data entered', u'100.00%'],
                [u'DISPOSITIF INTRA UTERIN (TCU 380 A) - DIU', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'no data entered', u'1462.40%'],
                [u'PARACETAMOL 500MG CP.', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'no data entered'],
                [u'EFAVIRENZ 600MG CP.', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'80.77%'],
                [u'RIFAMPICINE+ISONIAZIDE (150+75)MG CP.', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'no data entered', u'101.21%'],
                [u'Produit 15', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'100.00%'],
                [u'Produit 14', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'90.00%'],
                [u'ACETATE DE MEDROXY PROGESTERONE 150MG/ML+S A B KIT (1+1) (DEPO-PROVERA)', u'no data entered',
                 u'no data entered', u'no data entered', u'no data entered', u'no data entered', u'150.00%'],
                [u'Produit 2', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'100.00%'],
                [u'ACT PETIT ENFANT', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'100.00%'],
                [u'Produit 1', u'no data entered', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered'],
                [u'ALBENDAZOL 4% SB.', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'100.00%'],
                [u'LEVONORGESTREL+ETHYNILESTRADIOL+FER (0.15+0.03+75)MG (MICROGYNON)', u'no data entered',
                 u'no data entered', u'no data entered', u'no data entered', u'no data entered', u'222.22%'],
                [u'Produit C', u'93.88%', u'93.28%', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered'],
                [u'RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE (60+30+150)MG CP. DISPER', u'no data entered',
                 u'no data entered', u'no data entered', u'no data entered', u'no data entered', u'100.00%'],
                [u'TEST RAPIDE HIV 1/2 (SD BIOLINE)', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered', u'no data entered', u'100.00%'],
                [u'Produit B', u'98.28%', u'98.94%', u'no data entered', u'no data entered', u'no data entered',
                 u'no data entered']
            ], key=lambda x: x[0])
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

        self.assertEqual(
            headers,
            ['Product', 'October 2017', 'November 2017', 'December 2017', 'January 2018',
             'February 2018', 'March 2018']
        )
        self.assertItemsEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                [u'RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE+ETHAMBUTOL (150+75+400+2', u'0.00', u'0.00', u'0.00',
                 u'0.00', u'0.00', u'0.00'],
                [u'NEVIRAPINE 200MG CP.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'ACETATE DE MEDROXY PROGESTERONE 104MG/0.65ML INJ. (SAYANA PRESS)', u'0.00', u'0.00', u'0.00',
                 u'0.00', u'0.00', u'0.00'], [u'ACT ADULTE', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit A', u'442500.00', u'717500.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 10', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 12', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'LAMIVUDINE+NEVIRAPINE+ZIDOVUDINE (30+50+60)MG CP.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00',
                 u'0.00'],
                [u'DISPOSITIF INTRA UTERIN (TCU 380 A) - DIU', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00',
                 u'0.00'], [u'PARACETAMOL 500MG CP.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'EFAVIRENZ 600MG CP.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'RIFAMPICINE+ISONIAZIDE (150+75)MG CP.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 15', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 14', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'ACETATE DE MEDROXY PROGESTERONE 150MG/ML+S A B KIT (1+1) (DEPO-PROVERA)', u'0.00', u'0.00',
                 u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 2', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'ACT PETIT ENFANT', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit 1', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'ALBENDAZOL 4% SB.', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'LEVONORGESTREL+ETHYNILESTRADIOL+FER (0.15+0.03+75)MG (MICROGYNON)', u'0.00', u'0.00', u'0.00',
                 u'0.00', u'0.00', u'0.00'],
                [u'Produit C', u'198000.00', u'386400.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE (60+30+150)MG CP. DISPER', u'0.00', u'0.00', u'0.00',
                 u'0.00', u'0.00', u'0.00'],
                [u'TEST RAPIDE HIV 1/2 (SD BIOLINE)', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00', u'0.00'],
                [u'Produit B', u'336000.00', u'558000.00', u'0.00', u'0.00', u'0.00', u'0.00']
            ], key=lambda x: x[0])
        )
