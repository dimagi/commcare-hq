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
                            "all": 50,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of AWCs with a source of clean drinking water",
                            "percent": 107.1428571428571,
                            "value": 29,
                            "label": "AWCs with Clean Drinking Water"
                        },
                        {
                            "redirect": "functional_toilet",
                            "color": "green",
                            "all": 50,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "AWCs with functional toilet",
                            "percent": 87.5,
                            "value": 15,
                            "label": "AWCs with Functional Toilet"
                        }
                    ],
                    [
                        {
                            "redirect": "infants_weight_scale",
                            "color": "green",
                            "all": 50,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of AWCs with weighing scale for infants",
                            "percent": 140.0,
                            "value": 24,
                            "label": "AWCs with Weighing Scale: Infants"
                        },
                        {
                            "redirect": "adult_weight_scale",
                            "color": "green",
                            "all": 50,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of AWCs with weighing scale for mother and child",
                            "percent": 200.0,
                            "value": 9,
                            "label": "AWCs with Weighing Scale: Mother and Child"
                        }
                    ],
                    [
                        {
                            "redirect": "medicine_kit",
                            "color": "green",
                            "all": 50,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of AWCs with a Medicine Kit",
                            "percent": 81.81818181818183,
                            "value": 20,
                            "label": "AWCs with Medicine Kit"
                        }
                    ]
                ]
            }
        )
