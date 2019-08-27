from datetime import date

from corehq.apps.userreports.specs import EvaluationContext
from custom.intrahealth.tests.utils import TestDataSourceExpressions
from custom.intrahealth.utils import YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PRODUCT

VISITE_DE_L_OPERATOUR_PER_PRODUCT_DATA_SOURCE = 'visite_de_l_operateur_per_product.json'


class TestVisiteDeLOperatourPerProduct(TestDataSourceExpressions):

    data_source_name = VISITE_DE_L_OPERATOUR_PER_PRODUCT_DATA_SOURCE

    def test_visite_de_l_operatour_properties_for_post_test_xmlns(self):

        form = {
            'id': 'form_id',
            'xmlns': YEKSI_NAA_REPORTS_VISITE_DE_L_OPERATOUR_PER_PRODUCT,
            'domain': 'test-pna',
            'form': {
                'location_id': 'a025fa0f80c8451aabe5040c9dfc5efe',
                'region_name': 'Dakar',
                'PPS_name': 'PPS 1',
                'district_name': 'District Rufisque',
                'confirmed_products_update': {
                    'products_update': [
                        {
                            'question1': {
                                'loss_amt': 0,
                                'expired_pna_valuation': 0
                            },
                            'final_pna_stock': 1,
                            'final_pna_stock_valuation': 1,
                            'real_date_repeat': '2018-03-07',
                            'product_name': 'EFAVIRENZ 600MG CP.',
                            'product_id': '288a455ae0a0625f935374ff18aa4d20',
                            'site_code': 'dakar_rufisque_pps 1',
                            'PPS_name': 'PPS 1',
                        },
                        {
                            'question1': {
                                'loss_amt': 0,
                                'expired_pna_valuation': 0
                            },
                            'final_pna_stock': 1,
                            'final_pna_stock_valuation': 1,
                            'real_date_repeat': '2018-03-07',
                            'product_name': 'NEVIRAPINE 200MG CP.',
                            'product_id': '288a455ae0a0625f935374ff18a98a6d',
                            'site_code': 'dakar_rufisque_pps 1',
                            'PPS_name': 'PPS 1',
                        }
                    ],
                },
                'supply-point': 'fd79174541fa4f3b9924af69ee3db7ad',
                'site_code': 'dakar_rufisque_pps 1',
            }
        }

        user = {
            'id': 'user_id',
            'domain': 'test-pna',
            'location_id': 'test_location_id'
        }

        self.database.mock_docs = {
            'form_id': form,
            'user_id': user
        }

        pps_id = self.get_expression('pps_id', 'string')
        region_name = self.get_expression('region_name', 'string')
        pps_name = self.get_expression('pps_name', 'string')
        district_name = self.get_expression('district_name', 'string')
        supply_point = self.get_expression('supply-point', 'string')

        base_item_expression = self.get_expressions_from_base_item_expression()
        repeat_items = base_item_expression(form, EvaluationContext(form, 0))

        loss_amt = self.get_expression('loss_amt', 'integer')
        expired_pna_valuation = self.get_expression('expired_pna_valuation', 'integer')
        final_pna_stock = self.get_expression('final_pna_stock', 'integer')
        final_pna_stock_valuation = self.get_expression('final_pna_stock_valuation', 'integer')
        real_date_repeat = self.get_expression('real_date_repeat', 'date')
        product_name = self.get_expression('product_name', 'string')
        product_id = self.get_expression('product_id', 'string')
        site_code = self.get_expression('site_code', 'string')
        PPS_name = self.get_expression('PPS_name', 'string')

        self.assertEquals(pps_id(form, EvaluationContext(form, 0)), 'a025fa0f80c8451aabe5040c9dfc5efe')
        self.assertEquals(region_name(form, EvaluationContext(form, 0)), 'Dakar')
        self.assertEquals(pps_name(form, EvaluationContext(form, 0)), 'PPS 1')
        self.assertEquals(district_name(form, EvaluationContext(form, 0)), 'District Rufisque')
        self.assertEquals(supply_point(form, EvaluationContext(form, 0)), 'fd79174541fa4f3b9924af69ee3db7ad')

        self.assertEquals(loss_amt(repeat_items[0], EvaluationContext(repeat_items[0], 0)), 0)
        self.assertEquals(expired_pna_valuation(repeat_items[0], EvaluationContext(repeat_items[0], 0)), 0)
        self.assertEquals(final_pna_stock(repeat_items[0], EvaluationContext(repeat_items[0], 0)), 1)
        self.assertEquals(final_pna_stock_valuation(repeat_items[0], EvaluationContext(repeat_items[0], 0)), 1)
        self.assertEquals(
            real_date_repeat(repeat_items[0], EvaluationContext(repeat_items[0], 0)),
            date(2018, 3, 1)
        )
        self.assertEquals(
            product_name(repeat_items[0], EvaluationContext(repeat_items[0], 0)),
            'EFAVIRENZ 600MG CP.'
        )
        self.assertEquals(
            product_id(repeat_items[0], EvaluationContext(repeat_items[0], 0)),
            '288a455ae0a0625f935374ff18aa4d20'
        )
        self.assertEquals(
            site_code(repeat_items[0], EvaluationContext(repeat_items[0], 0)),
            'dakar_rufisque_pps 1'
        )
        self.assertEquals(PPS_name(repeat_items[1], EvaluationContext(repeat_items[1], 0)), 'PPS 1')
        self.assertEquals(loss_amt(repeat_items[1], EvaluationContext(repeat_items[1], 0)), 0)
        self.assertEquals(expired_pna_valuation(repeat_items[1], EvaluationContext(repeat_items[1], 0)), 0)
        self.assertEquals(final_pna_stock(repeat_items[1], EvaluationContext(repeat_items[1], 0)), 1)
        self.assertEquals(final_pna_stock_valuation(repeat_items[1], EvaluationContext(repeat_items[1], 0)), 1)
        self.assertEquals(
            real_date_repeat(repeat_items[1], EvaluationContext(repeat_items[1], 0)),
            date(2018, 3, 1)
        )
        self.assertEquals(
            product_name(repeat_items[1], EvaluationContext(repeat_items[1], 0)),
            'NEVIRAPINE 200MG CP.'
        )
        self.assertEquals(
            product_id(repeat_items[1], EvaluationContext(repeat_items[1], 0)),
            '288a455ae0a0625f935374ff18a98a6d'
        )
        self.assertEquals(
            site_code(repeat_items[1], EvaluationContext(repeat_items[1], 0)),
            'dakar_rufisque_pps 1'
        )
        self.assertEquals(PPS_name(repeat_items[1], EvaluationContext(repeat_items[1], 0)), 'PPS 1')
