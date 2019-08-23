from datetime import date

from corehq.apps.userreports.specs import EvaluationContext
from custom.intrahealth.tests.utils import TestDataSourceExpressions

LOGISTICIEN_DATA_SOURCE = 'yeksi_naa_reports_logisticien.json'


class TestLogisticien(TestDataSourceExpressions):

    data_source_name = LOGISTICIEN_DATA_SOURCE

    def test_visite_de_l_operatour_properties_for_post_test_xmlns(self):
        case = {
            'district_id': '78f07d8fd2024dd48ecb45e4e9a64803',
            'district_name': 'THIES',
            'date_echeance': '2018-01-22',
            'montant_paye': 0,
            'montant_reel_a_payer': 0,
        }

        user = {
            'id': 'user_id',
            'domain': 'test-pna',
            'location_id': 'test_location_id'
        }

        self.database.mock_docs = {
            'user_id': user
        }

        district_id = self.get_expression('district_id', 'string')
        district_name = self.get_expression('district_name', 'string')
        montant_paye = self.get_expression('montant_paye', 'integer')
        montant_reel_a_payer = self.get_expression('montant_reel_a_payer', 'integer')
        date_echeance = self.get_expression('date_echeance', 'date')

        self.assertEquals(district_id(case, EvaluationContext(case, 0)), '78f07d8fd2024dd48ecb45e4e9a64803')
        self.assertEquals(district_name(case, EvaluationContext(case, 0)), 'THIES')
        self.assertEquals(montant_paye(case, EvaluationContext(case, 0)), 0)
        self.assertEquals(montant_reel_a_payer(case, EvaluationContext(case, 0)), 0)
        self.assertEquals(date_echeance(case, EvaluationContext(case, 0)), date(2018, 1, 1))
