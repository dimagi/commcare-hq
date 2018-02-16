from __future__ import absolute_import
from django.test import TestCase

from custom.icds_reports.reports.maternal_child import get_maternal_child_data


class TestMaternalChildData(TestCase):
    def test_data_underweight_weight_for_age(self):
        self.assertDictEqual(
            get_maternal_child_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][0][0],
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
            }
        )

    def test_data_wasting_weight_for_height(self):
        self.assertDictEqual(
            get_maternal_child_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][0][1],
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
                "percent": 41.935483870967715,
                "value": 8,
                "label": "Wasting (Weight-for-Height)"
            }
        )

    def test_data_stunting_height_for_age(self):
        self.assertDictEqual(
            get_maternal_child_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][1][0],
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
                "percent": -27.43055555555556,
                "value": 19,
                "label": "Stunting (Height-for-Age)"
            }
        )

    def test_data_newborns_with_low_birth_weight(self):
        self.assertDictEqual(
            get_maternal_child_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][1][1],
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
        )

    def test_data_early_initiation_of_breastfeeding(self):
        self.assertDictEqual(
            get_maternal_child_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][2][0],
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
            }
        )

    def test_data_exclusive_breastfeeding(self):
        self.assertDictEqual(
            get_maternal_child_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][2][1],
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
        )

    def test_data_children_initiated_appropriate_complementary_feeding(self):
        self.assertDictEqual(
            get_maternal_child_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][3][0],
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
                "percent": 147.27272727272728,
                "value": 34,
                "label": "Children initiated appropriate Complementary Feeding"
            }
        )

    def test_data_institutional_deliveries(self):
        self.assertDictEqual(
            get_maternal_child_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][3][1],
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
        )

    def test_data_records_length(self):
        self.assertEqual(
            len(get_maternal_child_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records']),
            4
        )

    def test_data_records_total_length(self):
        data = get_maternal_child_data(
            'icds-cas',
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )['records']

        self.assertEqual(
            sum([len(record_row) for record_row in data]),
            8
        )

    def test_data_keys(self):
        self.assertEqual(
            list(get_maternal_child_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            ).keys()),
            ['records']
        )
