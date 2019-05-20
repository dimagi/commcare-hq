from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from custom.icds_reports.reports.maternal_child import get_maternal_child_data
from custom.icds_reports.messages import new_born_with_low_weight_help_text, underweight_children_help_text, \
    early_initiation_breastfeeding_help_text, exclusive_breastfeeding_help_text, \
    children_initiated_appropriate_complementary_feeding_help_text


class TestMaternalChildData(TestCase):
    maxDiff = None
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
                "redirect": "maternal_and_child/underweight_children",
                "color": "green",
                "all": 696,
                "frequency": "month",
                "format": "percent_and_div",
                "help_text": underweight_children_help_text(),
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
                "redirect": "maternal_and_child/wasting",
                "color": "green",
                "all": 27,
                "frequency": "month",
                "format": "percent_and_div",
                "help_text": "Of the children enrolled for Anganwadi services, whose weight and height was "
                             "measured, the percentage of children between 0 - 5 years who were "
                             "moderately/severely wasted in the current month. "
                             "<br/><br/>"
                             "Severe Acute Malnutrition (SAM) or wasting in children is a symptom of acute "
                             "undernutrition usually as a consequence of insufficient food intake or a high "
                             "incidence of infectious diseases.",
                "percent": -11.111111111111109,
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
                },
                False,
                True
            )['records'][1][0],
            {
                "redirect": "maternal_and_child/stunting",
                "color": "green",
                "all": 32,
                "frequency": "month",
                "format": "percent_and_div",
                "help_text": "Of the children whose height was measured, the percentage of children between "
                             "0 - 5 years who were moderately/severely stunted in the current month."
                             "<br/><br/>"
                             "Stunting is a sign of chronic undernutrition and has long lasting harmful "
                             "consequences on the growth of a child",
                "percent": -14.236111111111107,
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
                "redirect": "maternal_and_child/low_birth",
                "color": "red",
                "all": 3,
                "frequency": "month",
                "format": "percent_and_div",
                "help_text": new_born_with_low_weight_help_text(html=False),
                "percent": "Data in the previous reporting period was 0",
                "value": 1,
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
                "redirect": "maternal_and_child/early_initiation",
                "color": "green",
                "all": 5,
                "frequency": "month",
                "format": "percent_and_div",
                "help_text": early_initiation_breastfeeding_help_text(),
                "percent": 20.000000000000018,
                "value": 2,
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
                "redirect": "maternal_and_child/exclusive_breastfeeding",
                "color": "green",
                "all": 50,
                "frequency": "month",
                "format": "percent_and_div",
                "help_text": exclusive_breastfeeding_help_text(),
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
                "redirect": "maternal_and_child/children_initiated",
                "color": "green",
                "all": 40,
                "frequency": "month",
                "format": "percent_and_div",
                "help_text": children_initiated_appropriate_complementary_feeding_help_text(),
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
                "redirect": "maternal_and_child/institutional_deliveries",
                "color": "green",
                "all": 14,
                "frequency": "month",
                "format": "percent_and_div",
                "help_text": "Of the total number of women enrolled for Anganwadi services who gave birth in "
                             "the last month, the percentage who delivered in a public or private medical "
                             "facility. Delivery in medical instituitions is associated with a decrease in "
                             "maternal mortality rate",
                "percent": 80.0,
                "value": 14,
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
