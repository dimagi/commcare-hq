from datetime import date
from corehq.apps.userreports.specs import EvaluationContext
from custom.champ.tests.utils import TestDataSourceExpressions
from custom.champ.utils import PREVENTION_XMLNS, TARGET_XMLNS

ENHANCED_PEER_MOBILIZATION_DATA_SOURCE = 'enhanced_peer_mobilization.json'


class TestEnhancedPeerMobilization(TestDataSourceExpressions):

    data_source_name = ENHANCED_PEER_MOBILIZATION_DATA_SOURCE

    def test_achievement_form_property(self):
        form = {
            'id': 'form_id',
            'xmlns': PREVENTION_XMLNS,
            'domain': 'champ_cameroon',
            'form': {
                'uic': 'test uic',
                'group': {
                    'age': 12,
                },
                'district': 'test district',
                'visit_date': '2017-01-15',
                'type_visit': 'first visit',
                'activity_type': 'test activity type',
                'client_type': 'test client',
                'want_hiv_test': 'yes',
                'meta': {
                    'userID': 'user_id'
                }
            }
        }

        user = {
            'id': 'user_id',
            'domain': 'champ_cameroon',
            'location_id': 'test_location_id'
        }

        self.database.mock_docs = {
            'form_id': form,
            'user_id': user
        }

        xmlns = self.get_expression('xmlns', 'string')
        uic = self.get_expression('uic', 'string')
        age = self.get_expression('age', 'integer')
        district = self.get_expression('district', 'string')
        user_id = self.get_expression('user_id', 'string')
        client_type = self.get_expression('client_type', 'string')
        kp_prev_month = self.get_expression('kp_prev_month', 'date')
        organization = self.get_expression('organization', 'string')
        want_hiv_test = self.get_expression('want_hiv_test', 'string')

        self.assertEquals(
            xmlns(form, EvaluationContext(form, 0)), PREVENTION_XMLNS
        )
        self.assertEquals(
            uic(form, EvaluationContext(form, 0)), 'test uic'
        )
        self.assertEquals(
            age(form, EvaluationContext(form, 0)), 12
        )
        self.assertEquals(
            district(form, EvaluationContext(form, 0)), 'test district'
        )
        self.assertEquals(
            user_id(form, EvaluationContext(form, 0)), 'user_id'
        )
        self.assertEquals(
            kp_prev_month(form, EvaluationContext(form, 0)), date(2017, 1, 1)
        )
        self.assertEquals(
            organization(form, EvaluationContext(form, 0)), 'test_location_id'
        )
        self.assertEquals(
            want_hiv_test(form, EvaluationContext(form, 0)), 'yes'
        )
        self.assertEquals(
            client_type(form, EvaluationContext(form, 0)), 'test client'
        )

    def test_target_form_properties(self):
        form = {
            'id': 'form_id',
            'xmlns': TARGET_XMLNS,
            'domain': 'champ_cameroon',
            'form': {
                'locations': {
                    'district': 'test district',
                    'cbo': 'test cbo',
                    'clienttype': 'fsw_test_client_type',
                    'userpl': 'test userpl'
                },
                'fiscal_year': '2017',
                'target_kp_prev': 15,
                'target_htc_tst': 54,
                'target_htc_pos': 35,
                'target_care_new': 16,
                'target_tx_new': 11,
                'target_tx_undetect': 20
            }
        }

        district = self.get_expression('district', 'string')
        cbo = self.get_expression('cbo', 'string')
        clienttype = self.get_expression('clienttype', 'string')
        userpl = self.get_expression('userpl', 'string')
        fiscal_year = self.get_expression('fiscal_year', 'integer')
        target_kp_prev = self.get_expression('target_kp_prev', 'integer')
        target_htc_tst = self.get_expression('target_htc_tst', 'integer')
        target_htc_pos = self.get_expression('target_htc_pos', 'integer')
        target_care_new = self.get_expression('target_care_new', 'integer')
        target_tx_new = self.get_expression('target_tx_new', 'integer')
        target_tx_undetect = self.get_expression('target_tx_undetect', 'integer')

        self.assertEquals(
            district(form, EvaluationContext(form, 0)), 'test district'
        )
        self.assertEquals(
            cbo(form, EvaluationContext(form, 0)), 'test cbo'
        )
        self.assertEquals(
            clienttype(form, EvaluationContext(form, 0)), 'fsw'
        )
        self.assertEquals(
            userpl(form, EvaluationContext(form, 0)), 'test userpl'
        )
        self.assertEquals(
            fiscal_year(form, EvaluationContext(form, 0)), '2017'
        )
        self.assertEquals(
            target_kp_prev(form, EvaluationContext(form, 0)), 15
        )
        self.assertEquals(
            target_htc_tst(form, EvaluationContext(form, 0)), 54
        )
        self.assertEquals(
            target_htc_pos(form, EvaluationContext(form, 0)), 35
        )
        self.assertEquals(
            target_care_new(form, EvaluationContext(form, 0)), 16
        )
        self.assertEquals(
            target_tx_new(form, EvaluationContext(form, 0)), 11
        )
        self.assertEquals(
            target_tx_undetect(form, EvaluationContext(form, 0)), 20
        )
