from __future__ import absolute_import
from __future__ import unicode_literals
from custom.champ.tests.utils import ChampTestCase
from custom.champ.views import ServiceUptakeView

import json
import mock

from django.urls import reverse


class TestServiceUptake(ChampTestCase):

    def setUp(self):
        super(TestServiceUptake, self).setUp()
        self.view = ServiceUptakeView.as_view()
        self.url = 'service_uptake'

    def test_report_only_months_filters(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})
        filters = {
            'month_start': 1,
            'month_end': 1,
            'year_start': 2018,
            'year_end': 2018
        }
        request = self.factory.post(
            working_reverse,
            data=json.dumps(filters),
            content_type='application/json'
        )
        request.user = self.user
        response = self.view(request, domain=self.domain.name)
        content = json.loads(response.content)
        expected_data_htc_uptake = {
            "color": "blue",
            "values": [{"y": 0.3909327387588257, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_uptake"
        }
        expected_data_htc_yield = {
            "color": "orange",
            "values": [{"y": 0.09125475285171103, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_yield"
        }
        expected_data_link_to_care = {
            "color": "gray",
            "values": [{"y": 2.0208333333333335, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "Link to care"
        }
        expected_tick_values = [1514764800000]

        self.assertDictEqual(expected_data_htc_uptake, content['chart'][0])
        self.assertDictEqual(expected_data_htc_yield, content['chart'][1])
        self.assertDictEqual(expected_data_link_to_care, content['chart'][2])
        self.assertListEqual(expected_tick_values, content['tickValues'])

    def test_report_filter_by_district(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})
        filters = {
            'month_start': 1,
            'month_end': 1,
            'year_start': 2018,
            'year_end': 2018,
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
        expected_data_htc_uptake = {
            "color": "blue",
            "values": [{"y": 0.0034762456546929316, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_uptake"
        }
        expected_data_htc_yield = {
            "color": "orange",
            "values": [{"y": 1.0, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_yield"
        }
        expected_data_link_to_care = {
            "color": "gray",
            "values": [{"y": 1.3333333333333333, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "Link to care"
        }
        expected_tick_values = [1514764800000]

        self.assertDictEqual(expected_data_htc_uptake, content['chart'][0])
        self.assertDictEqual(expected_data_htc_yield, content['chart'][1])
        self.assertDictEqual(expected_data_link_to_care, content['chart'][2])
        self.assertListEqual(expected_tick_values, content['tickValues'])

    def test_report_filter_by_type_visit(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})
        filters = {
            'month_start': 1,
            'month_end': 1,
            'year_start': 2018,
            'year_end': 2018,
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
        expected_data_htc_uptake = {
            "color": "blue",
            "values": [{"y": 0.511175898931001, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_uptake"
        }
        expected_data_htc_yield = {
            "color": "orange",
            "values": [{"y": 0.09125475285171103, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_yield"
        }
        expected_data_link_to_care = {
            "color": "gray",
            "values": [{"y": 2.0208333333333335, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "Link to care"
        }
        expected_tick_values = [1514764800000]

        self.assertDictEqual(expected_data_htc_uptake, content['chart'][0])
        self.assertDictEqual(expected_data_htc_yield, content['chart'][1])
        self.assertDictEqual(expected_data_link_to_care, content['chart'][2])
        self.assertListEqual(expected_tick_values, content['tickValues'])

    def test_report_filter_by_activity_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})
        filters = {
            'month_start': 1,
            'month_end': 1,
            'year_start': 2018,
            'year_end': 2018,
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
        expected_data_htc_uptake = {
            "color": "blue",
            "values": [{"y": 0.44899701237729406, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_uptake"
        }
        expected_data_htc_yield = {
            "color": "orange",
            "values": [{"y": 0.09125475285171103, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_yield"
        }
        expected_data_link_to_care = {
            "color": "gray",
            "values": [{"y": 2.0208333333333335, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "Link to care"
        }
        expected_tick_values = [1514764800000]

        self.assertDictEqual(expected_data_htc_uptake, content['chart'][0])
        self.assertDictEqual(expected_data_htc_yield, content['chart'][1])
        self.assertDictEqual(expected_data_link_to_care, content['chart'][2])
        self.assertListEqual(expected_tick_values, content['tickValues'])

    def test_report_filter_by_client_type(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})
        filters = {
            'month_start': 1,
            'month_end': 1,
            'year_start': 2018,
            'year_end': 2018,
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
        expected_data_htc_uptake = {
            "color": "blue",
            "values": [{"y": 0.45468509984639016, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_uptake"
        }
        expected_data_htc_yield = {
            "color": "orange",
            "values": [{"y": 0.11824324324324324, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_yield"
        }
        expected_data_link_to_care = {
            "color": "gray",
            "values": [{"y": 0.6571428571428571, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "Link to care"
        }
        expected_tick_values = [1514764800000]

        self.assertDictEqual(expected_data_htc_uptake, content['chart'][0])
        self.assertDictEqual(expected_data_htc_yield, content['chart'][1])
        self.assertDictEqual(expected_data_link_to_care, content['chart'][2])
        self.assertListEqual(expected_tick_values, content['tickValues'])

    def test_report_filter_by_organization(self):
        if self.factory is None:
            return
        working_reverse = reverse(self.url, kwargs={'domain': self.domain.name})
        filters = {
            'month_start': 1,
            'month_end': 1,
            'year_start': 2018,
            'year_end': 2018,
            'district': ['biyem_assi', 'nylon']
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
        expected_data_htc_uptake = {
            "color": "blue",
            "values": [{"y": 0, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_uptake"
        }
        expected_data_htc_yield = {
            "color": "orange",
            "values": [{"y": 0, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "HTC_yield"
        }
        expected_data_link_to_care = {
            "color": "gray",
            "values": [{"y": 0, "x": 1514764800000}],
            "strokeWidth": 2,
            "classed": "dashed",
            "key": "Link to care"
        }

        expected_tick_values = [1514764800000]

        self.assertDictEqual(expected_data_htc_uptake, content['chart'][0])
        self.assertDictEqual(expected_data_htc_yield, content['chart'][1])
        self.assertDictEqual(expected_data_link_to_care, content['chart'][2])
        self.assertListEqual(expected_tick_values, content['tickValues'])
