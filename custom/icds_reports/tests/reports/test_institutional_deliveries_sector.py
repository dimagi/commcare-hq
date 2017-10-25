from django.test.utils import override_settings

from custom.icds_reports.reports.institutional_deliveries_sector import get_institutional_deliveries_data_map, \
    get_institutional_deliveries_data_chart, get_institutional_deliveries_sector_data
from django.test import TestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestInstitutionalDeliveriesSector(TestCase):

    def test_map_data(self):
        self.assertDictEqual(
            get_institutional_deliveries_data_map(
                'icds-cas',
                config={
                    'month': (2017, 5, 1),
                    'aggregation_level': 1
                },
                loc_level='state'
            )[0],
            {
                "rightLegend": {
                    "info": "Percentage of pregnant women who delivered in a public or "
                            "private medical facility in the last month. <br/><br/>Delivery in medical"
                            " instituitions is associated with a decrease in maternal mortality rate",
                    "average": 76.92307692307692
                },
                "fills": {
                    "0%-20%": "#de2d26",
                    "20%-60%": "#fc9272",
                    "60%-100%": "#fee0d2",
                    "defaultFill": "#9D9D9D"
                },
                "data": {
                    "st1": {
                        "all": 13,
                        "children": 9,
                        "fillKey": "60%-100%"
                    },
                    "st2": {
                        "all": 13,
                        "children": 11,
                        "fillKey": "60%-100%"
                    }
                },
                "slug": "institutional_deliveries",
                "label": "Percent Instituitional Deliveries"
            }
        )

    def test_chart_data(self):
        self.assertDictEqual(
            get_institutional_deliveries_data_chart(
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
                        "loc_name": "st2",
                        "percent": 84.61538461538461
                    },
                    {
                        "loc_name": "st1",
                        "percent": 69.23076923076923
                    }
                ],
                "top_five": [
                    {
                        "loc_name": "st2",
                        "percent": 84.61538461538461
                    },
                    {
                        "loc_name": "st1",
                        "percent": 69.23076923076923
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
                                "y": 0.3,
                                "x": 1491004800000,
                                "all": 20,
                                "in_month": 6
                            },
                            {
                                "y": 0.7692307692307693,
                                "x": 1493596800000,
                                "all": 26,
                                "in_month": 20
                            }
                        ],
                        "key": "% Institutional deliveries"
                    }
                ],
                "all_locations": [
                    {
                        "loc_name": "st2",
                        "percent": 84.61538461538461
                    },
                    {
                        "loc_name": "st1",
                        "percent": 69.23076923076923
                    }
                ]
            }
        )

    def test_sector_data(self):
        self.assertDictEqual(
            get_institutional_deliveries_sector_data(
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
                "info": "Percentage of pregnant women who delivered in a public or private medical "
                        "facility in the last month. <br/><br/>Delivery in medical instituitions"
                        " is associated with a decrease in maternal mortality rate",
                "tooltips_data": {
                    "s2": {
                        "all": 0,
                        "children": 0
                    },
                    "s1": {
                        "all": 2,
                        "children": 1
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
                                0.5
                            ],
                            [
                                "s2",
                                0.0
                            ]
                        ],
                        "key": ""
                    }
                ]
            }
        )
