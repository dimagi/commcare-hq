from __future__ import absolute_import
from __future__ import unicode_literals
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
                "help_text": "Of the total children enrolled for Anganwadi services and weighed, "
                             "the percentage of children between 0-5 years who were moderately/severely "
                             "underweight in the current month. Children who are moderately or severely "
                             "underweight have a higher risk of mortality. ",
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
                },
                False,
                True
            )['records'][0][1],
            {
                "redirect": "wasting",
                "color": "green",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "help_text": "Of the children enrolled for Anganwadi services, whose weight and height was "
                             "measured, the percentage of children between 0 - 5 years enrolled who were "
                             "moderately/severely wasted in the current month. "
                             "<br/><br/>"
                             "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute "
                             "undernutrition usually as a consequence of insufficient food intake or a high "
                             "incidence of infectious diseases.",
                "percent": 0,
                "value": 1,
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
                },
                False,
                True
            )['records'][1][0],
            {
                "redirect": "stunting",
                "color": "red",
                "all": 0,
                "frequency": "month",
                "format": "percent_and_div",
                "help_text": "Of the children whose height was measured, the percentage of children between "
                             "0 - 5 years who were moderately/severely stunted in the current month."
                             "<br/><br/>"
                             "Stunting is a sign of chronic undernutrition and has long lasting harmful "
                             "consequences on the growth of a child",
                "percent": "Data in the previous reporting period was 0",
                "value": 0,
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
                "help_text": "Of all the children born and weighed in the current month and enrolled for "
                             "Anganwadi services, the percentage that had a birth weight less than 2500 grams. "
                             "Newborns with Low Birth Weight are closely associated with fetal and neonatal "
                             "mortality and morbidity, inhibited growth and cognitive development, and chronic "
                             "diseases later in life. ",
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
                "help_text": "Of the children born in the last month and enrolled for Anganwadi services, "
                             "the percentage whose breastfeeding was initiated within 1 hour of delivery. "
                             "Early initiation of breastfeeding ensure the newborn recieves the \"first milk\" "
                             "rich in nutrients and encourages exclusive breastfeeding practice",
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
                "help_text": "Of the total children enrolled for Anganwadi services between the ages of "
                             "0 to 6 months, the percentage that was exclusively fed with breast milk. "
                             "An infant is exclusively breastfed if they receive only breastmilk with no "
                             "additional food or liquids (even water), ensuring optimal nutrition and growth "
                             "between 0 - 6 months",
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
                "help_text": "Of the total children enrolled for Anganwadi services between the ages of "
                             "6 to 8 months, the percentage that was given a timely introduction to solid, "
                             "semi-solid or soft food. Timely intiation of complementary feeding in addition "
                             "to breastmilk at 6 months of age is a key feeding practice to reduce malnutrition",
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
                "help_text": "Of the total number of women enrolled for Anganwadi services who gave birth in "
                             "the last month, the percentage who delivered in a public or private medical "
                             "facility. Delivery in medical instituitions is associated with a decrease in "
                             "maternal mortality rate",
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
