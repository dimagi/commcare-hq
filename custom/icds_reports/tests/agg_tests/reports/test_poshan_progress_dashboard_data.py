from django.test import TestCase

from custom.icds_reports.reports.poshan_progress_dashboard_data import get_poshan_progress_dashboard_data


class TestPPDData(TestCase):

    def test_get_ppr_data_comparitive_month(self):
        self.maxDiff = None
        data = get_poshan_progress_dashboard_data(
            'icds-cas',
            2017,
            5,
            2,
            'month',
            'comparitive',
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
                        [{'Best performers': [{'place': 'd1', 'value': '35.25%'}],
                          'Worst performers': [{'place': 'd1',
                                                'value': '35.25%'}],
                          'indicator': 'Take Home Ration'},
                         {'Best performers': [{'place': 'd1', 'value': '0.83%'}],
                          'Worst performers': [{'place': 'd1', 'value': '0.83%'}],
                          'indicator': 'Supplementary Nutrition'}]]}
        self.assertDictEqual(expected, data)

    def test_get_ppr_data_comparitive_quarter(self):
        self.maxDiff = None
        data = get_poshan_progress_dashboard_data(
            'icds-cas',
            2017,
            None,
            2,
            'quarter',
            'comparitive',
            {
                'aggregation_level': 1,
            },
            False
        )
        expected = {'ICDS CAS Coverage': [[{'Best performers': [{'place': 'st1',
                                                                 'value': '52.00%'},
                                                                {'place': 'st2',
                                                                 'value': '36.36%'},
                                                                {'place': 'st1',
                                                                 'value': '142.40%'}],
                                            'Worst performers': [{'place': 'st3',
                                                                  'value': '0.00%'},
                                                                 {'place': 'st3',
                                                                  'value': '0.00%'},
                                                                 {'place': 'st4',
                                                                  'value': '0.00%'}],
                                            'indicator': 'AWC Open'},
                                           {'Best performers': [{'place': 'st1', 'value': '1.62%'},
                                                                {'place': 'st1', 'value': '0.00%'},
                                                                {'place': 'st2',
                                                                 'value': '0.00%'}],
                                            'Worst performers': [{'place': 'st1',
                                                                  'value': '0.00%'},
                                                                 {'place': 'st2',
                                                                  'value': '0.00%'},
                                                                 {'place': 'st2',
                                                                  'value': '0.00%'}],
                                            'indicator': 'Home Visits'}]],
                    'Service Delivery': [[{'Best performers': [{'place': 'st2', 'value': '5.08%'},
                                                               {'place': 'st1', 'value': '3.62%'},
                                                               {'place': 'st2',
                                                                'value': '11.64%'}],
                                           'Worst performers': [{'place': 'st3', 'value': '0.00%'},
                                                                {'place': 'st3', 'value': '0.00%'},
                                                                {'place': 'st4',
                                                                 'value': '0.00%'}],
                                           'indicator': 'Pre-school Education'},
                                          {'Best performers': [{'place': 'st2', 'value': '73.68%'},
                                                               {'place': 'st1', 'value': '68.01%'},
                                                               {'place': 'st2',
                                                                'value': '67.18%'}],
                                           'Worst performers': [{'place': 'st3', 'value': '0.00%'},
                                                                {'place': 'st3', 'value': '0.00%'},
                                                                {'place': 'st4',
                                                                 'value': '0.00%'}],
                                           'indicator': 'Weighing efficiency'}],
                                         [{'Best performers': [{'place': 'st2', 'value': '4.87%'},
                                                               {'place': 'st1', 'value': '1.47%'},
                                                               {'place': 'st1', 'value': '1.41%'}],
                                           'Worst performers': [{'place': 'st3', 'value': '0.00%'},
                                                                {'place': 'st3', 'value': '0.00%'},
                                                                {'place': 'st4',
                                                                 'value': '0.00%'}],
                                           'indicator': 'Height Measurement Efficiency'},
                                          {'Best performers': [{'place': 'st1', 'value': '72.97%'},
                                                               {'place': 'st2', 'value': '71.43%'},
                                                               {'place': 'st1',
                                                                'value': '42.31%'}],
                                           'Worst performers': [{'place': 'st3', 'value': '0.00%'},
                                                                {'place': 'st3', 'value': '0.00%'},
                                                                {'place': 'st4',
                                                                 'value': '0.00%'}],
                                           'indicator': 'Counselling'}],
                                         [{'Best performers': [{'place': 'st2', 'value': '66.88%'},
                                                               {'place': 'st1', 'value': '35.25%'},
                                                               {'place': 'st2',
                                                                'value': '10.43%'}],
                                           'Worst performers': [{'place': 'st1', 'value': '0.00%'},
                                                                {'place': 'st3', 'value': '0.00%'},
                                                                {'place': 'st3',
                                                                 'value': '0.00%'}],
                                           'indicator': 'Take Home Ration'},
                                          {'Best performers': [{'place': 'st2', 'value': '2.37%'},
                                                               {'place': 'st1', 'value': '1.49%'},
                                                               {'place': 'st1', 'value': '0.83%'}],
                                           'Worst performers': [{'place': 'st2', 'value': '0.00%'},
                                                                {'place': 'st3', 'value': '0.00%'},
                                                                {'place': 'st3',
                                                                 'value': '0.00%'}],
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
                                          'Number of States Covered': 7},
                    'Service Delivery': {
                        '% of children between 3-6 years provided PSE for atleast 21+ days': '6.66%',
                        '% of children between 3-6 years provided SNP for atleast 21+ days': '1.61%',
                        '% of children between 6 months -3 years, P&LW provided THR for atleast 21+ days': '52.90%',
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
        expected = {'ICDS CAS Coverage': {'% Number of Days AWC Were opened': '78.13%',
                                          '% of Home Visits': '0.32%',
                                          'Number of AWCs Launched': 15,
                                          'Number of Blocks Covered': 3,
                                          'Number of Districts Covered': 3,
                                          'Number of States Covered': 5},
                    'Service Delivery': {
                        '% of children between 3-6 years provided PSE for atleast 21+ days': '5.53%',
                        '% of children between 3-6 years provided SNP for atleast 21+ days': '1.23%',
                        '% of children between 6 months -3 years, P&LW provided THR for atleast 21+ days': '28.27%',
                        '% of trimester three women counselled on immediate and EBF': '59.09%',
                        'Height Measurement Efficiency': '2.24%',
                        'Weighing efficiency': '68.96%'}}
        self.assertDictEqual(expected, data)
