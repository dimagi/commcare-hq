from django.test.utils import override_settings

from django.urls.base import reverse

from custom.icds_reports.tests.reports.report_test_case import ReportTestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class TestAdhaar(ReportTestCase):

    def test_map_data(self):
        response = self.client.get(reverse('adhaar', kwargs={'domain': 'icds-cas', 'step': 'map'}), data=dict(
            location_id=None,
            month=5,
            year=2017
        ))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                'report_data': [{
                    "rightLegend": {
                        "info": "Percentage of individuals registered using CAS "
                                "whose Adhaar identification has been captured",
                        "average": 26.2
                    },
                    "fills": {
                        "0%-25%": "#de2d26",
                        "25%-50%": "#fc9272",
                        "50%-100%": "#fee0d2",
                        "defaultFill": "#9D9D9D"
                    },
                    "data": {
                        "st1": {
                            "in_month": 64,
                            "all": 221,
                            "fillKey": "25%-50%"
                        },
                        "st2": {
                            "in_month": 67,
                            "all": 279,
                            "fillKey": "0%-25%"
                        }
                    },
                    "slug": "adhaar",
                    "label": "Percent Adhaar-seeded Beneficiaries"
                }]
            }
        )

    def test_chart_data(self):
        response = self.client.get(reverse('adhaar', kwargs={'domain': 'icds-cas', 'step': 'chart'}), data=dict(
            location_id=None,
            month=5,
            year=2017
        ))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                'report_data': {
                    "location_type": "State",
                    "bottom_five": [
                        {
                            "loc_name": "st1",
                            "percent": 28.959276018099548
                        },
                        {
                            "loc_name": "st2",
                            "percent": 24.014336917562723
                        }
                    ],
                    "top_five": [
                        {
                            "loc_name": "st1",
                            "percent": 28.959276018099548
                        },
                        {
                            "loc_name": "st2",
                            "percent": 24.014336917562723
                        }
                    ],
                    "chart_data": [
                        {
                            "color": "#006fdf",
                            "classed": "dashed",
                            "strokeWidth": 2,
                            "values": [
                                {
                                    "y": 0.0,
                                    "x": 1485907200000,
                                    "all": 0
                                },
                                {
                                    "y": 0.0,
                                    "x": 1488326400000,
                                    "all": 0
                                },
                                {
                                    "y": 0.25,
                                    "x": 1491004800000,
                                    "all": 484
                                },
                                {
                                    "y": 0.262,
                                    "x": 1493596800000,
                                    "all": 500
                                }
                            ],
                            "key": "Percentage of beneficiaries with Adhaar numbers"
                        }
                    ],
                    "all_locations": [
                        {
                            "loc_name": "st1",
                            "percent": 28.959276018099548
                        },
                        {
                            "loc_name": "st2",
                            "percent": 24.014336917562723
                        }
                    ]
                }
            }
        )

    def test_sector_data(self):
        response = self.client.get(reverse('adhaar', kwargs={'domain': 'icds-cas', 'step': 'map'}), data=dict(
            location_id='b1',
            month=5,
            year=2017
        ))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                'report_data': {
                    "info": "Percentage of individuals registered using "
                            "CAS whose Adhaar identification has been captured",
                    "tooltips_data": {
                        "s2": {
                            "in_month": 21,
                            "all": 66
                        },
                        "s1": {
                            "in_month": 23,
                            "all": 34
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
                                    0.6764705882352942
                                ],
                                [
                                    "s2",
                                    0.3181818181818182
                                ]
                            ],
                            "key": ""
                        }
                    ]
                }
            }
        )
