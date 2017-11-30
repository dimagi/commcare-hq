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
                            "all": 30,
                            "format": "percent_and_div",
                            "color": "red",
                            "percent": -3.3333333333333286,
                            "value": 29,
                            "label": "AWCs Reported Clean Drinking Water",
                            "frequency": "month",
                            "help_text": "Percentage of AWCs that reported having a source of clean drinking water"
                        },
                        {
                            "redirect": "functional_toilet",
                            "all": 30,
                            "format": "percent_and_div",
                            "color": "red",
                            "percent": -12.499999999999995,
                            "value": 15,
                            "label": "AWCs Reported Functional Toilet",
                            "frequency": "month",
                            "help_text": "Percentage of AWCs that reported having a functional toilet"
                        }
                    ],
                    [
                        {
                            "redirect": "infants_weight_scale",
                            "all": 30,
                            "format": "percent_and_div",
                            "color": "green",
                            "percent": 11.999999999999996,
                            "value": 24,
                            "label": "AWCs Reported Weighing Scale: Infants",
                            "frequency": "month",
                            "help_text": "Percentage of AWCs that reported having a weighing scale for infants"
                        },
                        {
                            "redirect": "adult_weight_scale",
                            "all": 30,
                            "format": "percent_and_div",
                            "color": "green",
                            "percent": 40.00000000000001,
                            "value": 9,
                            "label": "AWCs Reported Weighing Scale: Mother and Child",
                            "frequency": "month",
                            "help_text": "Percentage of AWCs that reported having"
                                         " a weighing scale for mother and child"
                        }
                    ],
                    [
                        {
                            "redirect": "medicine_kit",
                            "all": 30,
                            "format": "percent_and_div",
                            "color": "red",
                            "percent": -15.15151515151516,
                            "value": 20,
                            "label": "AWCs Reported Medicine Kit",
                            "frequency": "month",
                            "help_text": "Percentage of AWCs that reported having a Medicine Kit"
                        }
                    ]
                ]
            }
        )
