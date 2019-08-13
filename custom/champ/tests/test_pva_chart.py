from __future__ import absolute_import
from __future__ import unicode_literals
import json
import mock

from custom.champ.tests.utils import ChampTestCase
from custom.champ.views import PrevisionVsAchievementsView

from django.urls import reverse


class TestPVAChart(ChampTestCase):

    def setUp(self):
        super(TestPVAChart, self).setUp()
        self.view = PrevisionVsAchievementsView.as_view()
        self.url = 'champ_pva'

    def test_target_indicators_fiscal_year_2018(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'target_fiscal_year': 2018
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {
            "color": "blue",
            "values": [
                {"y": 17800, "x": "KP_PREV"},
                {"y": 179476, "x": "HTC_TST"},
                {"y": 145632, "x": "HTC_POS"},
                {"y": 391068, "x": "CARE_NEW"},
                {"y": 708758, "x": "TX_NEW"},
                {"y": 19353, "x": "TX_UNDETECT"}
            ],
            "key": "Target"
        }
        self.assertDictEqual(expected_data, content['chart'][0])

    def test_target_indicators_fiscal_year_2017(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'target_fiscal_year': 2017
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {
            "color": "blue",
            "values": [
                {"y": 0, "x": "KP_PREV"},
                {"y": 0, "x": "HTC_TST"},
                {"y": 0, "x": "HTC_POS"},
                {"y": 0, "x": "CARE_NEW"},
                {"y": 0, "x": "TX_NEW"},
                {"y": 0, "x": "TX_UNDETECT"}
            ],
            "key": "Target"
        }
        self.assertDictEqual(expected_data, content['chart'][0])

    def test_target_indicators_district(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'target_fiscal_year': 2018,
            'target_district': ['new_bell', 'bamenda']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {
            "color": "blue",
            "values": [
                {"y": 237, "x": "KP_PREV"},
                {"y": 35544, "x": "HTC_TST"},
                {"y": 127943, "x": "HTC_POS"},
                {"y": 333801, "x": "CARE_NEW"},
                {"y": 128966, "x": "TX_NEW"},
                {"y": 3093, "x": "TX_UNDETECT"}
            ],
            "key": "Target"
        }
        self.assertDictEqual(expected_data, content['chart'][0])

    def test_target_indicators_cbo(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'target_fiscal_year': 2018,
            'target_cbo': ['alternatives_deido', 'cmwa_bda']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {
            "color": "blue",
            "values": [
                {"y": 61, "x": "KP_PREV"},
                {"y": 2563, "x": "HTC_TST"},
                {"y": 1254, "x": "HTC_POS"},
                {"y": 3256, "x": "CARE_NEW"},
                {"y": 123, "x": "TX_NEW"},
                {"y": 1452, "x": "TX_UNDETECT"}
            ],
            "key": "Target"
        }
        self.assertDictEqual(expected_data, content['chart'][0])

    def test_target_indicators_client_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'target_fiscal_year': 2018,
            'target_clienttype': ['client_fsw']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {
            "color": "blue",
            "values": [
                {"y": 3704, "x": "KP_PREV"},
                {"y": 15270, "x": "HTC_TST"},
                {"y": 3834, "x": "HTC_POS"},
                {"y": 10378, "x": "CARE_NEW"},
                {"y": 16057, "x": "TX_NEW"},
                {"y": 7362, "x": "TX_UNDETECT"}
            ],
            "key": "Target"
        }
        self.assertDictEqual(expected_data, content['chart'][0])

    def test_target_indicators_userpl(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'target_fiscal_year': 2018,
            'target_userpl': ['pl_7_cfsw_horizfemdla_deido', 'pl_4_msm_affirmatives_bda']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {
            "color": "blue",
            "values": [
                {"y": 3, "x": "KP_PREV"},
                {"y": 0, "x": "HTC_TST"},
                {"y": 0, "x": "HTC_POS"},
                {"y": 0, "x": "CARE_NEW"},
                {"y": 0, "x": "TX_NEW"},
                {"y": 0, "x": "TX_UNDETECT"}
            ],
            "key": "Target"
        }
        self.assertDictEqual(expected_data, content['chart'][0])

    def test_kp_prev_indicator_age(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'kp_prev_age': ['10-14 yrs']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 2, 'x': 'KP_PREV'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][0])

    def test_kp_prev_indicator_district(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'kp_prev_district': ['biyem_assi']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 400, 'x': 'KP_PREV'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][0])

    def test_kp_prev_indicator_activity_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'kp_prev_activity_type': 'epm'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 2343, 'x': 'KP_PREV'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][0])

    def test_kp_prev_indicator_type_visit(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'kp_prev_visit_type': 'first_visit'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 2058, 'x': 'KP_PREV'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][0])

    def test_kp_prev_indicator_client_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'kp_prev_client_type': ['FSW']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 1302, 'x': 'KP_PREV'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][0])

    def test_kp_prev_indicator_visit_date(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'kp_prev_visit_date': '2018-01-05 - 2018-01-07'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 145, 'x': 'KP_PREV'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][0])

    def test_kp_prev_indicator_user_group(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'kp_prev_user_group': ['test_group']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        with mock.patch(
                'custom.champ.views.get_user_ids_for_group',
                return_value=['336ba1e522dcaf023f006e376b530725', 'a2c9a0848d7806b76e2ed0ae7ea89c97']
        ):
            response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 53, 'x': 'KP_PREV'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][0])

    def test_kp_prev_indicator_want_hiv_test(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'kp_prev_want_hiv_test': 'yes'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 682, 'x': 'KP_PREV'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][0])

    def test_htc_tst_indicator_age_range(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'htc_tst_age_range': ['15-19 yrs', '25-50 yrs']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 169, 'x': 'HTC_TST'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][1])

    def test_htc_tst_indicator_district(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'htc_tst_district': ['biyem_assi']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 3, 'x': 'HTC_TST'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][1])

    def test_htc_tst_indicator_client_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'htc_tst_client_type': ['FSW']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 596, 'x': 'HTC_TST'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][1])

    def test_htc_tst_indicator_user_group(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})
        filters = {
            'htc_tst_user_group': ['test_group']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        with mock.patch(
                'custom.champ.views.get_user_ids_for_group',
                return_value=['336ba1e522dcaf023f006e376b530725', 'a2c9a0848d7806b76e2ed0ae7ea89c97']
        ):
            response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 30, 'x': 'HTC_TST'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][1])

    def test_htc_tst_indicator_posttest_date(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'htc_tst_post_date': '2018-01-05 - 2018-01-20'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 678, 'x': 'HTC_TST'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][1])

    def test_htc_tst_indicator_hiv_test_date(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'htc_tst_hiv_test_date': '2018-01-05 - 2018-01-20'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 606, 'x': 'HTC_TST'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][1])

    def test_htc_pos_indicator_age_range(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'htc_pos_age_range': ['15-19 yrs', '25-50 yrs']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 6, 'x': 'HTC_POS'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][2])

    def test_htc_pos_indicator_district(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'htc_pos_district': ['biyem_assi']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 3, 'x': 'HTC_POS'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][2])

    def test_htc_pos_indicator_client_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'htc_pos_client_type': ['FSW']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 72, 'x': 'HTC_POS'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][2])

    def test_htc_pos_indicator_user_group(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})
        filters = {
            'htc_pos_user_group': ['test_group']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        with mock.patch(
                'custom.champ.views.get_user_ids_for_group',
                return_value=['336ba1e522dcaf023f006e376b530725', 'a2c9a0848d7806b76e2ed0ae7ea89c97']
        ):
            response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 4, 'x': 'HTC_POS'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][2])

    def test_htc_pos_indicator_posttest_date(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'htc_pos_post_date': '2018-01-05 - 2018-01-20'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 33, 'x': 'HTC_POS'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][2])

    def test_htc_pos_indicator_hiv_test_date(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'htc_pos_hiv_test_date': '2018-01-05 - 2018-01-20'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 34, 'x': 'HTC_POS'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][2])

    def test_care_new_indicator_age_range(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'care_new_age_range': ['15-19 yrs', '25-50 yrs']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 18, 'x': 'CARE_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][3])

    def test_care_new_indicator_district(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'care_new_district': ['biyem_assi']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 4, 'x': 'CARE_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][3])

    def test_care_new_indicator_client_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'care_new_client_type': ['FSW']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 53, 'x': 'CARE_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][3])

    def test_care_new_indicator_user_group(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})
        filters = {
            'care_new_user_group': ['test_group']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        with mock.patch(
                'custom.champ.views.get_user_ids_for_group',
                return_value=['cc3f2de870bb43229d188904127e1923', 'c8c65f9a814f4f5f99ee8a4cbad9f17e']
        ):
            response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 62, 'x': 'CARE_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][3])

    def test_care_new_indicator_hiv_status(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'care_new_hiv_status': 'positive'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 210, 'x': 'CARE_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][3])

    def test_care_new_indicator_date_handshake(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'care_new_date_handshake': '2018-01-05 - 2018-01-20'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 116, 'x': 'CARE_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][3])

    def test_tx_new_indicator_age_range(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'tx_new_age_range': ['15-19 yrs', '25-50 yrs']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 6, 'x': 'TX_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][4])

    def test_tx_new_indicator_district(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'tx_new_district': ['biyem_assi']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 5, 'x': 'TX_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][4])

    def test_tx_new_indicator_client_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'tx_new_client_type': ['FSW']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 33, 'x': 'TX_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][4])

    def test_tx_new_indicator_user_group(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})
        filters = {
            'tx_new_user_group': ['test_group']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        with mock.patch(
                'custom.champ.views.get_user_ids_for_group',
                return_value=['336ba1e522dcaf023f006e376b530725', 'a2c9a0848d7806b76e2ed0ae7ea89c97']
        ):
            response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 3, 'x': 'TX_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][4])

    def test_tx_new_indicator_hiv_status(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'tx_new_hiv_status': 'positive'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 91, 'x': 'TX_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][4])

    def test_tx_new_indicator_first_art_date(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'tx_new_first_art_date': '2018-01-05 - 2018-01-20'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 2, 'x': 'TX_NEW'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][4])

    def test_tx_undetect_indicator_age_range(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'tx_undetect_age_range': ['15-19 yrs', '25-50 yrs']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 1, 'x': 'TX_UNDETECT'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][5])

    def test_tx_undetect_indicator_district(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'tx_undetect_district': ['biyem_assi']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 7, 'x': 'TX_UNDETECT'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][5])

    def test_tx_undetect_indicator_client_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'tx_undetect_client_type': ['FSW']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 90, 'x': 'TX_UNDETECT'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][5])

    def test_tx_undetect_indicator_user_group(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})
        filters = {
            'tx_undetect_user_group': ['test_group']
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        with mock.patch(
                'custom.champ.views.get_user_ids_for_group',
                return_value=['336ba1e522dcaf023f006e376b530725', 'a2c9a0848d7806b76e2ed0ae7ea89c97']
        ):
            response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 9, 'x': 'TX_UNDETECT'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][5])

    def test_tx_undetect_indicator_hiv_status(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'tx_undetect_hiv_status': 'positive'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 141, 'x': 'TX_UNDETECT'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][5])

    def test_tx_undetect_indicator_date_last_vl_test(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'tx_undetect_date_last_vl_test': '2018-01-05 - 2018-01-20'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 29, 'x': 'TX_UNDETECT'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][5])

    def test_tx_undetect_indicator_undetect_vl(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'undetect_vl': 'yes'
        }

        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {'y': 141, 'x': 'TX_UNDETECT'}
        self.assertDictEqual(expected_data, content['chart'][1]['values'][5])
