from __future__ import absolute_import
from __future__ import unicode_literals
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
from custom.icds_reports.messages import percent_children_enrolled_help_text
from custom.icds_reports.reports.enrolled_children import get_enrolled_children_data_map, \
    get_enrolled_children_data_chart, get_enrolled_children_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestEnrolledChildren(TestCase):

    def test_map_data(self):

        self.assertDictEqual(
            get_enrolled_children_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "rightLegend": {
                    "info": percent_children_enrolled_help_text(age_label="0 - 6 years"),
                    "average": '100.00',
                    'extended_info': [
                        {
                            'indicator': 'Number of children (0 - 6 years) who are enrolled for Anganwadi '
                                         'Services:',
                            'value': "1,288"
                        },
                        {
                            'indicator': 'Total number of children (0 - 6 years) who are registered: ',
                            'value': "1,288"
                        },
                        {
                            'indicator': (
                                'Percentage of registered children (0 - 6 years) '
                                'who are enrolled for Anganwadi Services:'
                            ),
                            'value': '100.00%'
                        }
                    ]
                },
                "fills": {
                    "Children": MapColors.BLUE,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'st4': {'all': 0, 'valid': 0, 'original_name': ['st4'], 'fillKey': 'Children'},
                    'st5': {'all': 0, 'valid': 0, 'original_name': ['st5'], 'fillKey': 'Children'},
                    'st6': {'all': 0, 'valid': 0, 'original_name': ['st6'], 'fillKey': 'Children'},
                    'st7': {'all': 1, 'valid': 1, 'original_name': ['st7'], 'fillKey': 'Children'},
                    'st1': {'all': 618, 'valid': 618, 'original_name': ['st1'], 'fillKey': 'Children'},
                    'st2': {'all': 669, 'valid': 669, 'original_name': ['st2'], 'fillKey': 'Children'},
                    'st3': {'all': 0, 'valid': 0, 'original_name': ['st3'], 'fillKey': 'Children'}
                },
                "slug": "enrolled_children",
                "label": ""
            }
        )

    def test_map_name_is_different_data(self):
        self.assertDictEqual(
            get_enrolled_children_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'aggregation_level': 3
                },
                loc_level='block',
            ),
            {
                "rightLegend": {
                    "info": percent_children_enrolled_help_text(age_label="0 - 6 years"),
                    "average": '100.00',
                    'extended_info': [
                        {
                            'indicator': 'Number of children (0 - 6 years) who are enrolled for Anganwadi '
                                         'Services:',
                            'value': "618"
                        },
                        {
                            'indicator': 'Total number of children (0 - 6 years) who are registered: ',
                            'value': "618"
                        },
                        {
                            'indicator': (
                                'Percentage of registered children (0 - 6 years) '
                                'who are enrolled for Anganwadi Services:'
                            ),
                            'value': '100.00%'
                        }
                    ]
                },
                "fills": {
                    "Children": MapColors.BLUE,
                    "defaultFill": MapColors.GREY
                },
                "data": {
                    'block_map': {
                        'all': 618,
                        'valid': 618,
                        'original_name': ['b1', 'b2'],
                        'fillKey': 'Children'
                    }
                },
                "slug": "enrolled_children",
                "label": ""
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_enrolled_children_data_chart(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "chart_data": [
                    {
                        "color": ChartColors.BLUE,
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            {
                                "y": 5,
                                "x": "0-1 month",
                                "all": 1288
                            },
                            {
                                "y": 45,
                                "x": "1-6 months",
                                "all": 1288
                            },
                            {
                                "y": 51,
                                "x": "6-12 months",
                                "all": 1288
                            },
                            {
                                "y": 213,
                                "x": "1-3 years",
                                "all": 1288
                            },
                            {
                                "y": 974,
                                "x": "3-6 years",
                                "all": 1288
                            }
                        ],
                        "key": "Children (0-6 years) who are enrolled"
                    }
                ],
                "location_type": "State"
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_enrolled_children_sector_data(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'state_id': 'st1',
                    'district_id': 'd1',
                    'block_id': 'b1',
                    'aggregation_level': 4
                },
                location_id='b1',
                loc_level='supervisor'
            ),
            {
                "info": percent_children_enrolled_help_text(),
                "tooltips_data": {
                    "s2": {
                        'all': 214,
                        "valid": 214
                    },
                    "s1": {
                        'all': 103,
                        "valid": 103
                    }
                },
                "chart_data": [
                    {
                        "color": MapColors.BLUE,
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            [
                                "s1",
                                103
                            ],
                            [
                                "s2",
                                214
                            ]
                        ],
                        "key": ""
                    }
                ],
                "format": "number"
            }
        )
