from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import TestCase
import mock

from custom.icds_reports.utils.data_accessor import get_program_summary_data_with_retrying,\
    get_awc_covered_data_with_retrying


class DataAccessorTest(TestCase):
    side_effect = [
        {
            'records': [
                [
                    {'value': 0, 'all': 0},
                    {'value': 0, 'all': 0},
                ],
                [
                    {'value': 0, 'all': 0},
                    {'value': 0, 'all': 0},
                ],
                [
                    {'value': 0, 'all': 0},
                    {'value': 0, 'all': 0},
                ],
                [
                    {'value': 0, 'all': 0},
                    {'value': 0, 'all': 0},
                ],
            ]
        },
        {
            'records': [
                [
                    {'value': 1, 'all': 2},
                    {'value': 4, 'all': 12},
                ],
                [
                    {'value': 3, 'all': 4},
                    {'value': 1, 'all': 2},
                ],
                [
                    {'value': 6, 'all': 15},
                    {'value': 5, 'all': 21},
                ],
                [
                    {'value': 2, 'all': 2},
                    {'value': 4, 'all': 18},
                ],
            ]
        },
    ]

    defected_chart_data = {
        'all_locations': [
            {u'loc_name': u'st2', u'value': 0.0},
            {u'loc_name': u'st1', u'value': 0.0},
            {u'loc_name': u'st7', u'value': 0.0},
            {u'loc_name': u'st3', u'value': 0.0},
            {u'loc_name': u'st4', u'value': 0.0},
            {u'loc_name': u'st5', u'value': 0.0},
            {u'loc_name': u'st6', u'value': 0.0}],
    }

    valid_chart_data = {
        'all_locations': [
            {u'loc_name': u'st2', u'value': 0.0},
            {u'loc_name': u'st1', u'value': 16.0},
            {u'loc_name': u'st7', u'value': 0.0},
            {u'loc_name': u'st3', u'value': 21.0},
            {u'loc_name': u'st4', u'value': 0.0},
            {u'loc_name': u'st5', u'value': 10.0},
            {u'loc_name': u'st6', u'value': 0.0}],
    }

    defected_map_data = {
        u'data': {
            u'st4': {u'districts': 0, u'blocks': 0, u'awcs': 0, u'original_name': [u'st4'],
                     u'states': 0, u'supervisors': 0, u'fillKey': u'Not launched'},
            u'st5': {u'districts': 0, u'blocks': 0, u'awcs': 0, u'original_name': [u'st5'],
                     u'states': 0, u'supervisors': 0, u'fillKey': u'Not launched'},
            u'st6': {u'districts': 0, u'blocks': 0, u'awcs': 0, u'original_name': [u'st6'],
                     u'states': 0, u'supervisors': 0, u'fillKey': u'Not launched'},
            u'st7': {u'districts': 0, u'blocks': 0, u'awcs': 0, u'original_name': [u'st7'],
                     u'states': 0, u'supervisors': 0, u'fillKey': u'Launched'},
            u'st1': {u'districts': 0, u'blocks': 0, u'awcs': 0, u'original_name': [u'st1'],
                     u'states': 0, u'supervisors': 0, u'fillKey': u'Launched'},
            u'st2': {u'districts': 0, u'blocks': 0, u'awcs': 0, u'original_name': [u'st2'],
                     u'states': 0, u'supervisors': 0, u'fillKey': u'Launched'},
            u'st3': {u'districts': 0, u'blocks': 0, u'awcs': 0, u'original_name': [u'st3'],
                     u'states': 0, u'supervisors': 0, u'fillKey': u'Not launched'}
        },
        u'slug': u'awc_covered'}

    domain = 'icds-cas'
    config = {
        'month': (2017, 5, 1),
        'prev_month': (2017, 4, 1),
        'aggregation_level': 1
    }
    now = (2017, 6, 1)

    def test_retrying_data_for_maternal_child_data(self):
        step = 'maternal_child'
        with mock.patch(
            "custom.icds_reports.utils.data_accessor.get_maternal_child_data",
            side_effect=self.side_effect,
            autospec=True
        ) as get_maternal_child_data:
            get_program_summary_data_with_retrying(
                step, self.domain, self.config, self.now, False, True
            )
            self.assertEqual(get_maternal_child_data.call_count, 2)

    def test_retrying_data_for_cas_reach_data(self):
        step = 'icds_cas_reach'
        with mock.patch(
            "custom.icds_reports.utils.data_accessor.get_cas_reach_data",
            side_effect=self.side_effect,
            autospec=True
        ) as get_cas_reach_data:
            get_program_summary_data_with_retrying(
                step, self.domain, self.config, self.now, False, True
            )
            self.assertEqual(get_cas_reach_data.call_count, 2)

    def test_retrying_data_for_demographics_data(self):
        step = 'demographics'
        with mock.patch(
            "custom.icds_reports.utils.data_accessor.get_demographics_data",
            side_effect=self.side_effect,
            autospec=True
        ) as get_demographics_data:
            get_program_summary_data_with_retrying(
                step, self.domain, self.config, self.now, False, True
            )
            self.assertEqual(get_demographics_data.call_count, 2)

    def test_retrying_data_for_wc_infrastructure_data(self):
        step = 'awc_infrastructure'
        with mock.patch(
            "custom.icds_reports.utils.data_accessor.get_awc_infrastructure_data",
            side_effect=self.side_effect,
            autospec=True
        ) as get_awc_infrastructure:
            get_program_summary_data_with_retrying(
                step, self.domain, self.config, self.now, False, True
            )
            self.assertEqual(get_awc_infrastructure.call_count, 2)

    def test_retrying_data_for_awc_covered_chart(self):
        step = 'chart'
        get_awc_covered_data_with_retrying.clear(step, self.domain, self.config, 1, 'st1', True)
        with mock.patch(
            "custom.icds_reports.utils.data_accessor.get_awcs_covered_data_chart",
            return_value=self.defected_chart_data,
            autospec=True
        ) as get_awcs_covered_data_chart:
            get_awc_covered_data_with_retrying(
                step, self.domain, self.config, 1, 'st1', True
            )
            self.assertEqual(get_awcs_covered_data_chart.call_count, 3)

    def test_data_for_awc_covered_chart(self):
        step = 'chart'
        get_awc_covered_data_with_retrying.clear(step, self.domain, self.config, 1, 'st1', True)
        with mock.patch(
            "custom.icds_reports.utils.data_accessor.get_awcs_covered_data_chart",
            return_value=self.valid_chart_data,
            autospec=True
        ) as get_awcs_covered_data_chart:
            get_awc_covered_data_with_retrying(
                step, self.domain, self.config, 1, 'st1', True
            )
            self.assertEqual(get_awcs_covered_data_chart.call_count, 1)

    def test_retrying_data_for_awc_covered_map(self):
        step = 'map'
        get_awc_covered_data_with_retrying.clear(step, self.domain, self.config, 1, 'st1', True)
        with mock.patch(
            "custom.icds_reports.utils.data_accessor.get_awcs_covered_data_map",
            return_value=self.defected_map_data,
            autospec=True
        ) as get_awcs_covered_data_map:
            get_awc_covered_data_with_retrying(
                step, self.domain, self.config, 1, 'st1', True
            )
            self.assertEqual(get_awcs_covered_data_map.call_count, 3)
