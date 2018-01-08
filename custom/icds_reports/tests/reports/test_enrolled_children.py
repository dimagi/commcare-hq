from __future__ import absolute_import
from django.test.utils import override_settings

from custom.icds_reports.const import ChartColors, MapColors
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
                    "info": "Total number of children between the age "
                            "of (0 - 6 years) who are enrolled for ICDS services",
                    "average": 643.5,
                    "average_format": "number",
                    'extended_info': [
                        {
                            'indicator': 'Number of children (0 - 6 years) who are enrolled for ICDS services:',
                            'value': "1,287"
                        },
                        {
                            'indicator': 'Total number of children (0 - 6 years) who are registered: ',
                            'value': "1,287"
                        },
                        {
                            'indicator': (
                                'Percentage of registered children (0 - 6 years) '
                                'who are enrolled for ICDS services:'
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
                    "st1": {
                        "valid": 618,
                        "all": 618,
                        'original_name': ["st1"],
                        "fillKey": "Children"
                    },
                    "st2": {
                        "valid": 669,
                        "all": 669,
                        'original_name': ["st2"],
                        "fillKey": "Children"
                    }
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
                    "info": "Total number of children between the age "
                            "of (0 - 6 years) who are enrolled for ICDS services",
                    "average": 309.0,
                    "average_format": "number",
                    'extended_info': [
                        {
                            'indicator': 'Number of children (0 - 6 years) who are enrolled for ICDS services:',
                            'value': "618"
                        },
                        {
                            'indicator': 'Total number of children (0 - 6 years) who are registered: ',
                            'value': "618"
                        },
                        {
                            'indicator': (
                                'Percentage of registered children (0 - 6 years) '
                                'who are enrolled for ICDS services:'
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
                                "all": 1287
                            },
                            {
                                "y": 45,
                                "x": "1-6 months",
                                "all": 1287
                            },
                            {
                                "y": 51,
                                "x": "6-12 months",
                                "all": 1287
                            },
                            {
                                "y": 213,
                                "x": "1-3 years",
                                "all": 1287
                            },
                            {
                                "y": 973,
                                "x": "3-6 years",
                                "all": 1287
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
                "info": "Total number of children between the age"
                        " of 0 - 6 years who are enrolled for ICDS services",
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
