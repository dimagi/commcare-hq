from django.test import TestCase

from custom.icds_reports.reports.poshan_progress_dashboard_data import get_poshan_progress_dashboard_data


class TestPPDData(TestCase):

    def test_get_ppr_data_comparative_month(self):
        self.maxDiff = None
        data = get_poshan_progress_dashboard_data(
            'icds-cas',
            2017,
            5,
            2,
            'month',
            'comparative',
            {
                'aggregation_level': 2,
                'state_id': 'st1',
            },
            False
        )
        expected = {'ICDS CAS Coverage': [[{'Best performers': [{'place': 'd1',
                                                                 'value': '142.40%'}],
                                            'Worst performers': [{'place': 'd1',
                                                                  'value': '142.40%'}],
                                            'indicator': 'AWC Open'},
                                           {'Best performers': [{'place': 'd1', 'value': '1.62%'}],
                                            'Worst performers': [{'place': 'd1',
                                                                  'value': '1.62%'}],
                                            'indicator': 'Home Visits'}]],
                    'Service Delivery': [
                        [{'Best performers': [{'place': 'd1', 'value': '1.45%'}],
                          'Worst performers': [{'place': 'd1', 'value': '1.45%'}],
                          'indicator': 'Pre-school Education'},
                         {'Best performers': [{'place': 'd1', 'value': '66.74%'}],
                          'Worst performers': [{'place': 'd1',
                                                'value': '66.74%'}],
                          'indicator': 'Weighing efficiency'}],
                        [{'Best performers': [{'place': 'd1', 'value': '1.47%'}],
                          'Worst performers': [{'place': 'd1', 'value': '1.47%'}],
                          'indicator': 'Height Measurement Efficiency'},
                         {'Best performers': [{'place': 'd1', 'value': '72.97%'}],
                          'Worst performers': [{'place': 'd1',
                                                'value': '72.97%'}],
                          'indicator': 'Counselling'}],
                        [{'Best performers': [{'place': 'd1', 'value': '28.67%'}],
                          'Worst performers': [{'place': 'd1',
                                                'value': '28.67%'}],
                          'indicator': 'Take Home Ration'},
                         {'Best performers': [{'place': 'd1', 'value': '0.83%'}],
                          'Worst performers': [{'place': 'd1', 'value': '0.83%'}],
                          'indicator': 'Supplementary Nutrition'}]]}
        self.assertDictEqual(expected, data)

    def test_get_ppr_data_comparative_quarter(self):
        self.maxDiff = None
        data = get_poshan_progress_dashboard_data(
            'icds-cas',
            2017,
            None,
            2,
            'quarter',
            'comparative',
            {
                'aggregation_level': 1,
            },
            False
        )
        expected = {'ICDS CAS Coverage': [[{'Best performers': [{'place': 'st1',
                                                                 'value': '97.20%'},
                                                                {'place': 'st2',
                                                                 'value': '71.64%'},
                                                                {'place': 'st7',
                                                                 'value': '0.00%'}],
                                            'Worst performers': [{'place': 'st7',
                                                                  'value': '0.00%'},
                                                                 {'place': 'st2',
                                                                  'value': '71.64%'},
                                                                 {'place': 'st1',
                                                                  'value': '97.20%'}],
                                            'indicator': 'AWC Open'},
                                           {'Best performers': [{'place': 'st1', 'value': '0.66%'},
                                                                {'place': 'st2', 'value': '0.00%'},
                                                                {'place': 'st7',
                                                                 'value': '0.00%'}],
                                            'Worst performers': [{'place': 'st7',
                                                                  'value': '0.00%'},
                                                                 {'place': 'st2',
                                                                  'value': '0.00%'},
                                                                 {'place': 'st1',
                                                                  'value': '0.66%'}],
                                            'indicator': 'Home Visits'}]],
                    'Service Delivery': [[{'Best performers': [{'place': 'st2', 'value': '8.41%'},
                                                               {'place': 'st1', 'value': '2.52%'},
                                                               {'place': 'st7', 'value': '0.00%'}],
                                           'Worst performers': [{'place': 'st7', 'value': '0.00%'},
                                                                {'place': 'st1', 'value': '2.52%'},
                                                                {'place': 'st2',
                                                                 'value': '8.41%'}],
                                           'indicator': 'Pre-school Education'},
                                          {'Best performers': [{'place': 'st2', 'value': '70.40%'},
                                                               {'place': 'st1', 'value': '67.39%'},
                                                               {'place': 'st7', 'value': '0.00%'}],
                                           'Worst performers': [{'place': 'st7', 'value': '0.00%'},
                                                                {'place': 'st1', 'value': '67.39%'},
                                                                {'place': 'st2',
                                                                 'value': '70.40%'}],
                                           'indicator': 'Weighing efficiency'}],
                                         [{'Best performers': [{'place': 'st2', 'value': '2.89%'},
                                                               {'place': 'st1', 'value': '1.44%'},
                                                               {'place': 'st7', 'value': '0.00%'}],
                                           'Worst performers': [{'place': 'st7', 'value': '0.00%'},
                                                                {'place': 'st1', 'value': '1.44%'},
                                                                {'place': 'st2',
                                                                 'value': '2.89%'}],
                                           'indicator': 'Height Measurement Efficiency'},
                                          {'Best performers': [{'place': 'st1', 'value': '60.32%'},
                                                               {'place': 'st2', 'value': '57.97%'},
                                                               {'place': 'st7', 'value': '0.00%'}],
                                           'Worst performers': [{'place': 'st7', 'value': '0.00%'},
                                                                {'place': 'st2', 'value': '57.97%'},
                                                                {'place': 'st1',
                                                                 'value': '60.32%'}],
                                           'indicator': 'Counselling'}],
                                         [{'Best performers': [{'place': 'st2', 'value': '34.75%'},
                                                               {'place': 'st1', 'value': '14.60%'},
                                                               {'place': 'st7', 'value': '0.00%'}],
                                           'Worst performers': [{'place': 'st7', 'value': '0.00%'},
                                                                {'place': 'st1', 'value': '14.60%'},
                                                                {'place': 'st2',
                                                                 'value': '34.75%'}],
                                           'indicator': 'Take Home Ration'},
                                          {'Best performers': [{'place': 'st2', 'value': '1.20%'},
                                                               {'place': 'st1', 'value': '1.16%'},
                                                               {'place': 'st7', 'value': '0.00%'}],
                                           'Worst performers': [{'place': 'st7', 'value': '0.00%'},
                                                                {'place': 'st1', 'value': '1.16%'},
                                                                {'place': 'st2',
                                                                 'value': '1.20%'}],
                                           'indicator': 'Supplementary Nutrition'}]]}

        self.assertDictEqual(expected, data)

    def test_get_ppr_data_aggregated_month(self):
        self.maxDiff = None
        data = get_poshan_progress_dashboard_data(
            'icds-cas',
            2017,
            5,
            2,
            'month',
            'aggregated',
            {
                'aggregation_level': 1,
            },
            False
        )
        expected = {'ICDS CAS Coverage': {'% Number of Days AWC Were opened': '118.18%',
                                          '% of Home Visits': '0.79%',
                                          'Number of AWCs Launched': 22,
                                          'Number of Blocks Covered': 5,
                                          'Number of Districts Covered': 4,
                                          'Number of States Covered': 3},
                    'Service Delivery': {
                        '% of children between 3-6 years provided PSE for atleast 21+ days': '6.66%',
                        '% of children between 3-6 years provided SNP for atleast 21+ days': '1.61%',
                        '% of children between 6 months -3 years, P&LW provided THR for atleast 21+ days': '43.65%',
                        '% of trimester three women counselled on immediate and EBF': '72.15%',
                        'Height Measurement Efficiency': '3.24%',
                        'Weighing efficiency': '70.27%'}}
        self.assertDictEqual(expected, data)

    def test_get_ppr_data_aggregated_quarter(self):
        self.maxDiff = None
        data = get_poshan_progress_dashboard_data(
            'icds-cas',
            2017,
            None,
            2,
            'quarter',
            'aggregated',
            {
                'aggregation_level': 1,
            },
            False
        )
        expected = {'ICDS CAS Coverage': {'% Number of Days AWC Were opened': '80.00%',
                                          '% of Home Visits': '0.32%',
                                          'Number of AWCs Launched': 15,
                                          'Number of Blocks Covered': 3,
                                          'Number of Districts Covered': 3,
                                          'Number of States Covered': 2},
                    'Service Delivery': {
                        '% of children between 3-6 years provided PSE for atleast 21+ days': '5.53%',
                        '% of children between 3-6 years provided SNP for atleast 21+ days': '1.18%',
                        '% of children between 6 months -3 years, P&LW provided THR for atleast 21+ days': '25.17%',
                        '% of trimester three women counselled on immediate and EBF': '59.09%',
                        'Height Measurement Efficiency': '2.19%',
                        'Weighing efficiency': '68.91%'}}
        self.assertDictEqual(expected, data)
