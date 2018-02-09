from __future__ import absolute_import
from django.test import TestCase

from custom.icds_reports.reports.maternal_child import get_maternal_child_data


class TestMaternalChildData(TestCase):
    maxDiff = None

    def test_data(self):
        self.assertDictEqual(
            get_maternal_child_data(
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
                            "redirect": "underweight_children",
                            "color": "green",
                            "all": 696,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of children between 0-5 years enrolled for Anganwadi Services"
                                         " with weight-for-age less than -2 standard deviations"
                                         " of the WHO Child Growth Standards median. "
                                         "Children who are moderately or severely underweight"
                                         " have a higher risk of mortality.",
                            "percent": -14.901477832512326,
                            "value": 150,
                            "label": "Underweight (Weight-for-Age)"
                        },
                        {
                            "redirect": "wasting",
                            "color": "red",
                            "all": 31,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of children (6-60 months) with weight-for-height below"
                                         " -3 standard deviations of the WHO Child Growth Standards median. "
                                         "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of"
                                         " acute undernutrition usually as a consequence of insufficient "
                                         "food intake or a high incidence of infectious diseases.",
                            "percent": 41.93548387096772,
                            "value": 8,
                            "label": "Wasting (Weight-for-Height)"
                        }
                    ],
                    [
                        {
                            "redirect": "stunting",
                            "color": "green",
                            "all": 32,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of children (6-60 months) with height-for-age below -2Z"
                                         " standard deviations of the WHO Child Growth Standards median. "
                                         "Stunting is a sign of chronic undernutrition and has "
                                         "long lasting harmful consequences on the growth of a child",
                            "percent": -27.430555555555564,
                            "value": 19,
                            "label": "Stunting (Height-for-Age)"
                        },
                        {
                            "redirect": "low_birth",
                            "color": "red",
                            "all": 4,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of newborns born with birth weight less than 2500 grams."
                                         " Newborns with Low Birth Weight are closely associated "
                                         "with foetal and neonatal mortality and morbidity,"
                                         " inhibited growth and cognitive development,"
                                         " and chronic diseases later in life",
                            "percent": "Data in the previous reporting period was 0",
                            "value": 2,
                            "label": "Newborns with Low Birth Weight"
                        }
                    ],
                    [
                        {
                            "redirect": "early_initiation",
                            "color": "green",
                            "all": 7,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of children breastfed within an hour of birth. "
                                         "Early initiation of breastfeeding ensure the newborn "
                                         "recieves the 'first milk' rich in nutrients "
                                         "and encourages exclusive breastfeeding practice",
                            "percent": 128.57142857142856,
                            "value": 4,
                            "label": "Early Initiation of Breastfeeding"
                        },
                        {
                            "redirect": "exclusive_breastfeeding",
                            "color": "green",
                            "all": 50,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of children between 0 - 6 months exclusively breastfed. "
                                         "An infant is exclusively breastfed if they recieve only breastmilk "
                                         "with no additional food, liquids (even water) ensuring "
                                         "optimal nutrition and growth between 0 - 6 months",
                            "percent": 149.84615384615384,
                            "value": 28,
                            "label": "Exclusive Breastfeeding"
                        }
                    ],
                    [
                        {
                            "redirect": "children_initiated",
                            "color": "green",
                            "all": 40,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of children between 6 - 8 months given timely "
                                         "introduction to solid or semi-solid food. Timely intiation"
                                         " of complementary feeding in addition to breastmilk "
                                         "at 6 months of age is a key feeding practice to reduce malnutrition",
                            "percent": 147.27272727272725,
                            "value": 34,
                            "label": "Children initiated appropriate Complementary Feeding"
                        },
                        {
                            "redirect": "institutional_deliveries",
                            "color": "green",
                            "all": 26,
                            "frequency": "month",
                            "format": "percent_and_div",
                            "help_text": "Percentage of pregnant women who delivered in a public "
                                         "or private medical facility in the last month. "
                                         "Delivery in medical instituitions is associated "
                                         "with a decrease in maternal mortality rate",
                            "percent": 156.41025641025647,
                            "value": 20,
                            "label": "Institutional Deliveries"
                        }
                    ]
                ]
            }
        )
