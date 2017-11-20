from __future__ import absolute_import
from django.test import TestCase

from custom.icds_reports.reports.demographics_data import get_demographics_data


class TestDemographics(TestCase):

    def test_data(self):
        self.assertDictEqual(
            get_demographics_data(
                'icds-cas',
                (2017, 5, 28),
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
                            "color": "red",
                            "all": None,
                            "frequency": "month",
                            "format": "number",
                            "help_text": "Total number of households registered",
                            "percent": 0.0,
                            "value": 6964,
                            "label": "Registered Households",
                            'redirect': 'registered_household'
                        },
                        {
                            "color": "green",
                            "all": 500,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of ICDS beneficiaries whose"
                                         " Aadhaar identification has been captured",
                            "percent": 4.800000000000011,
                            "value": 131,
                            "label": "Percent Aadhaar-seeded Beneficiaries",
                            'redirect': 'adhaar'
                        }
                    ],
                    [
                        {
                            "color": "green",
                            "all": None,
                            "frequency": "month",
                            "format": "number",
                            "help_text": "Total number of children registered between the age of 0 - 6 years",
                            "percent": 1.9809825673534072,
                            "value": 1287,
                            "label": "Children (0-6 years)"
                        },
                        {
                            "redirect": "enrolled_children",
                            "color": "green",
                            "all": None,
                            "frequency": "month",
                            "format": "number",
                            "help_text": "Total number of children registered between "
                                         "the age of 0 - 6 years and enrolled for ICDS services",
                            "percent": 1.9809825673534072,
                            "value": 1287,
                            "label": "Children (0-6 years) enrolled for ICDS services"
                        }
                    ],
                    [
                        {
                            "color": "green",
                            "all": None,
                            "frequency": "month",
                            "format": "number",
                            "help_text": "Total number of pregnant women registered",
                            "percent": 49.03846153846153,
                            "value": 155,
                            "label": "Pregnant Women"
                        },
                        {
                            "redirect": "enrolled_women",
                            "color": "green",
                            "all": None,
                            "frequency": "month",
                            "format": "number",
                            "help_text": "Total number of pregnant women registered"
                                         " and enrolled for ICDS services",
                            "percent": 49.03846153846153,
                            "value": 155,
                            "label": "Pregnant Women enrolled for ICDS services"
                        }
                    ],
                    [
                        {
                            "color": "green",
                            "all": None,
                            "frequency": "month",
                            "format": "number",
                            "help_text": "Total number of lactating women registered",
                            "percent": 4.40251572327044,
                            "value": 166,
                            "label": "Lactating Women"
                        },
                        {
                            "redirect": "lactating_enrolled_women",
                            "color": "green",
                            "all": None,
                            "frequency": "month",
                            "format": "number",
                            "help_text": "Total number of lactating women registered"
                                         " and enrolled for ICDS services",
                            "percent": 4.40251572327044,
                            "value": 166,
                            "label": "Lactating Women enrolled for ICDS services"
                        }
                    ],
                    [
                        {
                            "color": "red",
                            "all": None,
                            "frequency": "month",
                            "format": "number",
                            "help_text": "Total number of adolescent girls (11 - 18 years) who are registered",
                            "percent": -17.543859649122805,
                            "value": 47,
                            "label": "Adolescent Girls (11-18 years)"
                        },
                        {
                            "redirect": "adolescent_girls",
                            "color": "red",
                            "all": None,
                            "frequency": "month",
                            "format": "number",
                            "help_text": "Total number of adolescent girls (11 - 18 years)"
                                         " who are registered and enrolled for ICDS services",
                            "percent": -17.543859649122805,
                            "value": 47,
                            "label": "Adolescent Girls (11-18 years) enrolled for ICDS services"
                        }
                    ]
                ]
            }
        )
