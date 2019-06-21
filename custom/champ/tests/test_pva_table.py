from __future__ import absolute_import
from __future__ import unicode_literals

from custom.champ.tests.utils import ChampTestCase
from custom.champ.views import PrevisionVsAchievementsTableView

import json
import mock

from django.core.urlresolvers import reverse


class TestPVATable(ChampTestCase):

    def setUp(self):
        super(TestPVATable, self).setUp()
        self.view = PrevisionVsAchievementsTableView.as_view()
        self.url = 'champ_pva_table'

    def test_report_all_data(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        request = self.factory.post(
            working_reverse,
            data=json.dumps({}),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data = {
            'target_kp_prev': 17800,
            'target_htc_tst': 179476,
            'target_htc_pos': 145632,
            'target_care_new': 391068,
            'target_tx_new': 708758,
            'target_tx_undetect': 19353,
            'kp_prev': 2691,
            'htc_tst': 1059,
            'htc_pos': 99,
            'care_new': 210,
            'tx_new': 91,
            'tx_undetect': 141,
        }
        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_district(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'district': ['biyem_assi', 'nylon']
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
            'target_kp_prev': 4960,
            'target_htc_tst': 126854,
            'target_htc_pos': 6275,
            'target_care_new': 44606,
            'target_tx_new': 146044,
            'target_tx_undetect': 3108,
            'kp_prev': 863,
            'htc_tst': 3,
            'htc_pos': 3,
            'care_new': 4,
            'tx_new': 19,
            'tx_undetect': 37,
        }

        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_cbo(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'cbo': ['alternatives_deido', 'cmwa_bda']
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
            'target_kp_prev': 61,
            'target_htc_tst': 2563,
            'target_htc_pos': 1254,
            'target_care_new': 3256,
            'target_tx_new': 123,
            'target_tx_undetect': 1452,
            'kp_prev': 2691,
            'htc_tst': 1059,
            'htc_pos': 99,
            'care_new': 210,
            'tx_new': 91,
            'tx_undetect': 141,
        }
        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_visit_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'visit_type': 'first_visit'
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
            'target_kp_prev': 17800,
            'target_htc_tst': 179476,
            'target_htc_pos': 145632,
            'target_care_new': 391068,
            'target_tx_new': 708758,
            'target_tx_undetect': 19353,
            'kp_prev': 2058,
            'htc_tst': 1059,
            'htc_pos': 99,
            'care_new': 210,
            'tx_new': 91,
            'tx_undetect': 141,
        }

        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_activity_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'activity_type': 'epm'
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
            'target_kp_prev': 17800,
            'target_htc_tst': 179476,
            'target_htc_pos': 145632,
            'target_care_new': 391068,
            'target_tx_new': 708758,
            'target_tx_undetect': 19353,
            'kp_prev': 2343,
            'htc_tst': 1059,
            'htc_pos': 99,
            'care_new': 210,
            'tx_new': 91,
            'tx_undetect': 141,
        }

        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_client_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'client_type': ['FSW']
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
            'target_kp_prev': 1360,
            'target_htc_tst': 127162,
            'target_htc_pos': 9807,
            'target_care_new': 45074,
            'target_tx_new': 147442,
            'target_tx_undetect': 3543,
            'kp_prev': 1302,
            'htc_tst': 596,
            'htc_pos': 72,
            'care_new': 53,
            'tx_new': 33,
            'tx_undetect': 90,
        }

        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_organization(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'organization': ['test_group']
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
        expected_data = {
            'target_kp_prev': 17800,
            'target_htc_tst': 179476,
            'target_htc_pos': 145632,
            'target_care_new': 391068,
            'target_tx_new': 708758,
            'target_tx_undetect': 19353,
            'kp_prev': 0,
            'htc_tst': 59,
            'htc_pos': 4,
            'care_new': 62,
            'tx_new': 0,
            'tx_undetect': 0,
        }
        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_fiscal_year(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'fiscal_year': 2017
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
            'target_kp_prev': 0,
            'target_htc_tst': 0,
            'target_htc_pos': 0,
            'target_care_new': 0,
            'target_tx_new': 0,
            'target_tx_undetect': 0,
            'kp_prev': 2691,
            'htc_tst': 1059,
            'htc_pos': 99,
            'care_new': 210,
            'tx_new': 91,
            'tx_undetect': 141,
        }

        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_visit_date(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'visit_date': '2018-01-01 - 2018-01-10'
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
            'target_kp_prev': 17800,
            'target_htc_tst': 179476,
            'target_htc_pos': 145632,
            'target_care_new': 391068,
            'target_tx_new': 708758,
            'target_tx_undetect': 19353,
            'kp_prev': 643,
            'htc_tst': 1059,
            'htc_pos': 99,
            'care_new': 210,
            'tx_new': 91,
            'tx_undetect': 141,
        }
        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_posttest_date(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'posttest_date': '2018-01-01 - 2018-01-10'
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
            'target_kp_prev': 17800,
            'target_htc_tst': 179476,
            'target_htc_pos': 145632,
            'target_care_new': 391068,
            'target_tx_new': 708758,
            'target_tx_undetect': 19353,
            'kp_prev': 2691,
            'htc_tst': 242,
            'htc_pos': 18,
            'care_new': 210,
            'tx_new': 91,
            'tx_undetect': 141,
        }

        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_first_art_date(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'first_art_date': '2018-01-01 - 2018-01-10'
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
            'target_kp_prev': 17800,
            'target_htc_tst': 179476,
            'target_htc_pos': 145632,
            'target_care_new': 391068,
            'target_tx_new': 708758,
            'target_tx_undetect': 19353,
            'kp_prev': 2691,
            'htc_tst': 1059,
            'htc_pos': 99,
            'care_new': 210,
            'tx_new': 1,
            'tx_undetect': 141,
        }

        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_date_handshake(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'date_handshake': '2018-01-01 - 2018-01-10'
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
            'target_kp_prev': 17800,
            'target_htc_tst': 179476,
            'target_htc_pos': 145632,
            'target_care_new': 391068,
            'target_tx_new': 708758,
            'target_tx_undetect': 19353,
            'kp_prev': 2691,
            'htc_tst': 1059,
            'htc_pos': 99,
            'care_new': 82,
            'tx_new': 91,
            'tx_undetect': 141,
        }

        self.assertDictEqual(expected_data, content)

    def test_report_filter_by_date_last_vl_test(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})

        filters = {
            'date_last_vl_test': '2018-01-01 - 2018-01-10'
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
            'target_kp_prev': 17800,
            'target_htc_tst': 179476,
            'target_htc_pos': 145632,
            'target_care_new': 391068,
            'target_tx_new': 708758,
            'target_tx_undetect': 19353,
            'kp_prev': 2691,
            'htc_tst': 1059,
            'htc_pos': 99,
            'care_new': 210,
            'tx_new': 91,
            'tx_undetect': 22,
        }

        self.assertDictEqual(expected_data, content)
