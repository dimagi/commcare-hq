from django.test.utils import override_settings

from custom.icds_reports.reports.immunization_coverage_data import get_immunization_coverage_data_map, \
    get_immunization_coverage_data_chart, get_immunization_coverage_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestImmunizationCoverage(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_immunization_coverage_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of children 1 year+ who have received complete immunization"
                            " as per National Immunization Schedule of India required by age 1.",
                    "average": 10.896898575020955
                },
                "fills": {
                    "0%-20%": "#de2d26",
                    "20%-60%": "#fc9272",
                    "60%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "all": 573,
                        "children": 85,
                        "fillKey": "0%-20%"
                    },
                    "st2": {
                        "all": 620,
                        "children": 45,
                        "fillKey": "0%-20%"
                    }
                },
                "slug": "institutional_deliveries",
                "label": "Percent Immunization Coverage at 1 year"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_immunization_coverage_data_chart(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            ),
            {
                "location_type": "State",
                "bottom_five": [
                    {
                        "loc_name": "st1",
                        "percent": 14.834205933682373
                    },
                    {
                        "loc_name": "st2",
                        "percent": 7.258064516129032
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st1",
                        "percent": 14.834205933682373
                    },
                    {
                        "loc_name": "st2",
                        "percent": 7.258064516129032
                    }
                ],
                "chart_data": [
                    {
                        "color": "#006fdf",
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            {
                                "y": 0,
                                "x": 1485907200000,
                                "all": 0,
                                "in_month": 0
                            },
                            {
                                "y": 0,
                                "x": 1488326400000,
                                "all": 0,
                                "in_month": 0
                            },
                            {
                                "y": 0.10765349032800672,
                                "x": 1491004800000,
                                "all": 1189,
                                "in_month": 128
                            },
                            {
                                "y": 0.10896898575020955,
                                "x": 1493596800000,
                                "all": 1193,
                                "in_month": 130
                            }
                        ],
                        "key": "% Children received complete immunizations by 1 year"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st1",
                        "percent": 14.834205933682373
                    },
                    {
                        "loc_name": "st2",
                        "percent": 7.258064516129032
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_immunization_coverage_sector_data(
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
                "info": "Percentage of children 1 year+ who have recieved complete "
                        "immunization as per National Immunization Schedule of India required by age 1",
                "tooltips_data": {
                    "s2": {
                        "all": 193,
                        "children": 3
                    },
                    "s1": {
                        "all": 100,
                        "children": 31
                    }
                },
                "chart_data": [
                    {
                        "color": "#006fdf",
                        "classed": "dashed",
                        "strokeWidth": 2,
                        "values": [
                            [
                                "s1",
                                0.31
                            ],
                            [
                                "s2",
                                0.015544041450777202
                            ]
                        ],
                        "key": ""
                    }
                ]
            }

        )
