from __future__ import absolute_import
from django.test import TestCase

from custom.icds_reports.reports.awc_infrastracture import get_awc_infrastructure_data


class TestAWCInfrastructure(TestCase):

    def test_data(self):
        self.assertDictEqual(
            get_awc_infrastructure_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            ),
            {
                "records": [
                    [
                        {
                            "redirect": "clean_water",
                            "color": "green",
                            "all": 20,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": (
                                "Percentage of AWCs that reported having a source of clean drinking water"
                            ),
                            "percent": 272.85714285714283,
                            "value": 29,
                            "label": "AWCs Reported Clean Drinking Water"
                        }, {
                            "redirect": "functional_toilet",
                            "color": "green",
                            "all": 20,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of AWCs that reported having a functional toilet",
                            "percent": 237.5,
                            "value": 15,
                            "label": "AWCs Reported Functional Toilet"
                        }
                    ],
                    [
                        {
                            "redirect": "infants_weight_scale",
                            "color": "green",
                            "all": 20,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of AWCs that reported having a weighing scale for infants",
                            "percent": 332.0,
                            "value": 24,
                            "label": "AWCs Reported Weighing Scale: Infants"
                        }, {
                            "redirect": "adult_weight_scale",
                            "color": "green",
                            "all": 20,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": (
                                "Percentage of AWCs that reported having a weighing scale for mother and child"
                            ),
                            "percent": 440.0000000000001,
                            "value": 9,
                            "label": "AWCs Reported Weighing Scale: Mother and Child"
                        }
                    ],
                    [
                        {
                            "redirect": "medicine_kit",
                            "color": "green",
                            "all": 20,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of AWCs that reported having a Medicine Kit",
                            "percent": 227.27272727272725,
                            "value": 20,
                            "label": "AWCs Reported Medicine Kit"
                        }
                    ]
                ]
            }
        )
