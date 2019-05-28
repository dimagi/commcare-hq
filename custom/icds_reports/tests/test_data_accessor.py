from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import TestCase
import mock

from custom.icds_reports.utils.data_accessor import get_program_summary_data, get_program_summary_data_with_retrying


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
