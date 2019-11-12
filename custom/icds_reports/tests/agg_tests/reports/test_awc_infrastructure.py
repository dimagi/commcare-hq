from django.test import TestCase

from custom.icds_reports.messages import awcs_reported_clean_drinking_water_help_text, \
    awcs_reported_functional_toilet_help_text, awcs_reported_weighing_scale_infants_help_text, \
    awcs_reported_weighing_scale_mother_and_child_help_text, awcs_reported_medicine_kit_help_text
from custom.icds_reports.reports.awc_infrastracture import get_awc_infrastructure_data


class TestAWCInfrastructure(TestCase):
    def test_data_AWCs_reported_clean_drinking_water(self):
        self.assertDictEqual(
            get_awc_infrastructure_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][0][0],
            {
                "redirect": "awc_infrastructure/clean_water",
                "all": 30,
                "format": "percent_and_div",
                "color": "red",
                "percent": -3.3333333333333286,
                "value": 29,
                "label": "AWCs Reported Clean Drinking Water",
                "frequency": "month",
                "help_text": awcs_reported_clean_drinking_water_help_text()
            }
        )

    def test_data_AWCs_reported_functional_toilet(self):
        self.assertDictEqual(
            get_awc_infrastructure_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][0][1],
            {
                "redirect": "awc_infrastructure/functional_toilet",
                "all": 30,
                "format": "percent_and_div",
                "color": "red",
                "percent": -12.499999999999995,
                "value": 15,
                "label": "AWCs Reported Functional Toilet",
                "frequency": "month",
                "help_text": awcs_reported_functional_toilet_help_text()
            }
        )

    def test_data_AWCs_reported_weighing_scale_infants(self):
        self.assertDictEqual(
            get_awc_infrastructure_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][1][0],
            {
                "redirect": "awc_infrastructure/infants_weight_scale",
                "all": 30,
                "format": "percent_and_div",
                "color": "green",
                "percent": 11.999999999999998,
                "value": 24,
                "label": "AWCs Reported Weighing Scale: Infants",
                "frequency": "month",
                "help_text": awcs_reported_weighing_scale_infants_help_text()
            }
        )

    def test_data_AWCs_reported_weighing_scale_mother_and_child(self):
        self.assertDictEqual(
            get_awc_infrastructure_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][1][1],
            {
                "redirect": "awc_infrastructure/adult_weight_scale",
                "all": 30,
                "format": "percent_and_div",
                "color": "green",
                "percent": 40.00000000000001,
                "value": 9,
                "label": "AWCs Reported Weighing Scale: Mother and Child",
                "frequency": "month",
                "help_text": awcs_reported_weighing_scale_mother_and_child_help_text()
            }
        )

    def test_data_AWCs_reported_medicine_kit(self):
        self.assertDictEqual(
            get_awc_infrastructure_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records'][2][0],
            {
                "redirect": "awc_infrastructure/medicine_kit",
                "all": 30,
                "format": "percent_and_div",
                "color": "red",
                "percent": -15.151515151515161,
                "value": 20,
                "label": "AWCs Reported Medicine Kit",
                "frequency": "month",
                "help_text": awcs_reported_medicine_kit_help_text()
            }
        )

    def test_data_records_length(self):
        self.assertEqual(
            len(get_awc_infrastructure_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            )['records']),
            3
        )

    def test_data_records_total_length(self):
        data = get_awc_infrastructure_data(
            'icds-cas',
            {
                'month': (2017, 5, 1),
                'prev_month': (2017, 4, 1),
                'aggregation_level': 1
            }
        )['records']

        self.assertEqual(
            sum([len(record_row) for record_row in data]),
            5
        )

    def test_data_keys(self):
        self.assertEqual(
            list(get_awc_infrastructure_data(
                'icds-cas',
                {
                    'month': (2017, 5, 1),
                    'prev_month': (2017, 4, 1),
                    'aggregation_level': 1
                }
            ).keys()),
            ['records']
        )
