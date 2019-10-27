from django.test import TestCase

from custom.icds_reports.const import AADHAR_SEEDED_BENEFICIARIES, CHILDREN_ENROLLED_FOR_ANGANWADI_SERVICES, \
    PREGNANT_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES, LACTATING_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES, \
    ADOLESCENT_GIRLS_ENROLLED_FOR_ANGANWADI_SERVICES
from custom.icds_reports.messages import percent_children_enrolled_help_text, \
    percent_pregnant_women_enrolled_help_text, percent_lactating_women_enrolled_help_text, \
    percent_adolescent_girls_enrolled_help_text
from custom.icds_reports.reports.demographics_data import get_demographics_data


class TestDemographics(TestCase):

    def test_data_monthly_format(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 6, 1),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        self.assertEqual(1, len(data))
        self.assertEqual(3, len(data['records']))
        self.assertEqual(2, len(data['records'][0]))
        self.assertEqual(2, len(data['records'][1]))
        self.assertEqual(2, len(data['records'][2]))

    def test_data_monthly_registered_household(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 6, 1),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/registered_household",
            "all": None,
            "format": "number",
            "color": "green",
            "percent": 0.2507163323782235,
            "value": 2799,
            "label": "Registered Households",
            "frequency": "month",
            "help_text": "Total number of households registered"
        }
        self.assertDictEqual(expected, data['records'][0][0])

    def test_data_monthly_adhaar(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 6, 1),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/adhaar",
            "all": 1610,
            "format": "percent_and_div",
            "color": "green",
            "percent": 10.049606069448492,
            "value": 346,
            "label": AADHAR_SEEDED_BENEFICIARIES,
            "frequency": "month",
            "help_text": "Of the total number of ICDS beneficiaries, the percentage whose Adhaar identification "
                         "has been captured. "
        }
        self.assertDictEqual(expected, data['records'][0][1])

    def test_data_monthly_enrolled_children(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 6, 1),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/enrolled_children",
            "all": 1288,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0.0,
            "value": 1288,
            "label": CHILDREN_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "month",
            "help_text": percent_children_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][1][0])

    def test_data_monthly_enrolled_women(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 6, 1),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/enrolled_women",
            "all": 155,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0.0,
            "value": 155,
            "label": PREGNANT_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "month",
            "help_text": percent_pregnant_women_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][1][1])

    def test_data_monthly_lactating_enrolled_women(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 6, 1),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            'redirect': 'demographics/lactating_enrolled_women',
            "all": 167,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0.0,
            "value": 167,
            "label": LACTATING_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "month",
            "help_text": percent_lactating_women_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][2][0])

    def test_data_monthly_adolescent_girls(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 6, 1),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/adolescent_girls",
            "all": 34,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0.0,
            "value": 34,
            "label": ADOLESCENT_GIRLS_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "month",
            "help_text": percent_adolescent_girls_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][2][1])

    def test_data_daily_format(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 29),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        self.assertEqual(1, len(data))
        self.assertEqual(3, len(data['records']))
        self.assertEqual(2, len(data['records'][0]))
        self.assertEqual(2, len(data['records'][1]))
        self.assertEqual(2, len(data['records'][2]))

    def test_data_daily_registered_household(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 29),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/registered_household",
            "all": None,
            "format": "number",
            "color": "red",
            "percent": 0,
            "value": 2799,
            "label": "Registered Households",
            "frequency": "day",
            "help_text": "Total number of households registered"
        }
        self.assertDictEqual(expected, data['records'][0][0])

    def test_data_daily_adhaar(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 29),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/adhaar",
            "all": 1609,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0,
            "value": 346,
            "label": AADHAR_SEEDED_BENEFICIARIES,
            "frequency": "day",
            "help_text": (
                "Of the total number of ICDS beneficiaries, the percentage whose Adhaar identification has been "
                "captured. "
            )
        }
        self.assertDictEqual(expected, data['records'][0][1])

    def test_data_daily_enrolled_children(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 29),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/enrolled_children",
            "all": 1287,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0,
            "value": 1287,
            "label": CHILDREN_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "day",
            "help_text": percent_children_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][1][0])

    def test_data_daily_enrolled_women(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 29),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/enrolled_women",
            "all": 155,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0,
            "value": 155,
            "label": PREGNANT_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "day",
            "help_text": percent_pregnant_women_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][1][1])

    def test_data_daily_lactating_enrolled_women(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 29),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/lactating_enrolled_women",
            "all": 167,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0,
            "value": 167,
            "label": LACTATING_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "day",
            "help_text": percent_lactating_women_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][2][0])

    def test_data_daily_adolescent_girls(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 29),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/adolescent_girls",
            "all": 34,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0,
            "value": 34,
            "label": ADOLESCENT_GIRLS_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "day",
            "help_text": percent_adolescent_girls_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][2][1])

    def test_data_daily_if_aggregation_script_fail_format(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 30),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        self.assertEqual(1, len(data))
        self.assertEqual(3, len(data['records']))
        self.assertEqual(2, len(data['records'][0]))
        self.assertEqual(2, len(data['records'][1]))
        self.assertEqual(2, len(data['records'][2]))

    def test_data_daily_if_aggregation_script_fail_registered_household(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 30),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/registered_household",
            "all": None,
            "format": "number",
            "color": "red",
            "percent": 0,
            "value": 2799,
            "label": "Registered Households",
            "frequency": "day",
            "help_text": "Total number of households registered"
        }
        self.assertDictEqual(expected, data['records'][0][0])

    def test_data_daily_if_aggregation_script_fail_adhaar(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 30),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/adhaar",
            "all": 1610,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0,
            "value": 346,
            "label": AADHAR_SEEDED_BENEFICIARIES,
            "frequency": "day",
            "help_text": (
                "Of the total number of ICDS beneficiaries, the percentage whose Adhaar identification has "
                "been captured. "
            )
        }
        self.assertDictEqual(expected, data['records'][0][1])

    def test_data_daily_if_aggregation_script_fail_enrolled_children(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 30),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/enrolled_children",
            "all": 1288,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0,
            "value": 1288,
            "label": CHILDREN_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "day",
            "help_text": percent_children_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][1][0])

    def test_data_daily_if_aggregation_script_fail_enrolled_women(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 30),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/enrolled_women",
            "all": 155,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0,
            "value": 155,
            "label": PREGNANT_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "day",
            "help_text": percent_pregnant_women_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][1][1])

    def test_data_daily_if_aggregation_script_fail_lactating_enrolled_women(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 30),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/lactating_enrolled_women",
            "all": 167,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0,
            "value": 167,
            "label": LACTATING_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "day",
            "help_text": percent_lactating_women_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][2][0])

    def test_data_daily_if_aggregation_script_fail_adolescent_girls(self):
        data = get_demographics_data(
            'icds-cas',
            (2017, 5, 30),
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )
        expected = {
            "redirect": "demographics/adolescent_girls",
            "all": 34,
            "format": "percent_and_div",
            "color": "red",
            "percent": 0,
            "value": 34,
            "label": ADOLESCENT_GIRLS_ENROLLED_FOR_ANGANWADI_SERVICES,
            "frequency": "day",
            "help_text": percent_adolescent_girls_enrolled_help_text()
        }
        self.assertDictEqual(expected, data['records'][2][1])
