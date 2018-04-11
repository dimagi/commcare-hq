from __future__ import absolute_import
from __future__ import unicode_literals
from mock.mock import MagicMock

from custom.yeksi_naa_reports.tests.utils import YeksiTestCase
from custom.yeksi_naa_reports.reports import Dashboard3Report


class TestDashboard3(YeksiTestCase):

    def test_valuation_of_pna_stock_per_product_data_report(self):
        mock = MagicMock()
        mock.couch_user = self.user
        mock.GET = {
            'location_id': '',
            'month_start': '1',
            'year_start': '2018',
            'month_end': '3',
            'year_end': '2018',
        }

        dashboard3_report = Dashboard3Report(request=mock, domain='test-pna')

        valuation_of_pna_stock_per_product_data_report = \
            dashboard3_report.report_context['reports'][0]['report_table']
        headers = valuation_of_pna_stock_per_product_data_report['headers'].as_export_table[0]
        rows = valuation_of_pna_stock_per_product_data_report['rows']

        self.assertEqual(
            headers,
            ['Product', 'January 2018', 'February 2018', 'March 2018']
        )
        self.assertItemsEqual(
            sorted(rows, key=lambda x: x[0]),
            sorted([
                ['NEVIRAPINE 200MG CP.', '0.00', '0.00', '0.00'],
                ['DISPOSITIF INTRA UTERIN (TCU 380 A) - DIU', '0.00', '0.00', '0.00'],
                ['RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE+ETHAMBUTOL (150+75+400+2', '0.00', '0.00', '0.00'],
                ['TEST RAPIDE HIV 1/2 (SD BIOLINE)', '0.00', '0.00', '0.00'],
                ['Produit 15', '0.00', '0.00', '0.00'],
                ['LEVONORGESTREL+ETHYNILESTRADIOL+FER (0.15+0.03+75)MG (MICROGYNON)', '0.00', '0.00', '0.00'],
                ['PARACETAMOL 500MG CP.', '0.00', '0.00', '0.00'],
                ['ALBENDAZOL 4% SB.', '0.00', '0.00', '0.00'],
                ['ACETATE DE MEDROXY PROGESTERONE 104MG/0.65ML INJ. (SAYANA PRESS)', '0.00', '0.00', '0.00'],
                ['ACT ADULTE', '0.00', '0.00', '0.00'],
                ['EFAVIRENZ 600MG CP.', '0.00', '0.00', '0.00'],
                ['Produit 14', '0.00', '0.00', '0.00'],
                ['Produit 10', '0.00', '0.00', '0.00'],
                ['ACETATE DE MEDROXY PROGESTERONE 150MG/ML+S A B KIT (1+1) (DEPO-PROVERA)',
                 '0.00', '0.00', '0.00'],
                ['RIFAMPICINE+ISONIAZIDE+PYRAZINAMIDE (60+30+150)MG CP. DISPER', '0.00', '0.00', '0.00'],
                ['Produit 2', '0.00', '0.00', '0.00'],
                ['RIFAMPICINE+ISONIAZIDE (150+75)MG CP.', '0.00', '0.00', '0.00'],
                ['Produit 12', '0.00', '0.00', '0.00'],
                ['ACT PETIT ENFANT', '0.00', '0.00', '0.00'],
                ['LAMIVUDINE+NEVIRAPINE+ZIDOVUDINE (30+50+60)MG CP.', '0.00', '0.00', '0.00'],
                ['Produit 1', '0.00', '0.00', '0.00']
            ], key=lambda x: x[0])
        )
