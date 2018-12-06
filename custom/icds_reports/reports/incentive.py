from __future__ import unicode_literals, absolute_import, division


from custom.icds_reports.models.aggregate import AWWIncentiveReport
from custom.icds_reports.utils import india_now

class IncentiveReport(object):

    def __init__(self, block, month):
        self.block = block
        self.month = month

    def get_excel_data(self):

        def _format_infrastructure_data(data):
            return data if data else 'Data not entered'

        data = AWWIncentiveReport.objects.filter(month=self.month, block_id=self.block).values('state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name', 'aww_name', 'contact_phone_number', 'wer_weighed', 'wer_eligible', 'awc_num_open', 'valid_visits', 'expected_visits')

        headers = ['State', 'District', 'Block', 'Supervisor', 'AWC', 'AWW Name', 'AWW Contact Number', 'Home Visits Conducted', 'Number of Days AWC was Open', 'Weighing Efficiency', 'Eligible for Incentive']

        excel_rows = []
        excel_rows.append(headers)
        for row in data:
            home_visit_percent = row['valid_visits'] / int(row['expected_visits']) if int(row['expected_visits']) else 1
            weighing_efficiency = row['wer_weighed'] / row['wer_eligible'] if row['wer_eligible'] else 1
            if home_visit_percent > 1:
                home_visit_percent = 1
            if row['awc_num_open'] is None:
                num_open = 'Data not entered'
            else:
                num_open = row['awc_num_open']

            excel_rows.append([row['state_name'],
                               row['district_name'],
                               row['block_name'],
                               row['supervisor_name'],
                               row['awc_name'],
                               _format_infrastructure_data(row['aww_name']),
                               _format_infrastructure_data(row['contact_phone_number']),
                               '{:.2%}'.format(home_visit_percent),
                               num_open,
                               '{:.2%}'.format(weighing_efficiency),
                               'Yes' if weighing_efficiency >= 0.6 and home_visit_percent >= 0.6 else 'No'])

        return [
            [
                'AWW Performance Report',
                excel_rows
            ],
            [
                'Export Info',
                [
                    ['Generated at', india_now()],
                    ['Grouped By', 'AWC'],
                    ['Month', self.month.month],
                    ['Year', self.month.year],
                    ['Disclaimer', "The information in the report is based on the self-reported data entered by the Anganwadi Worker in ICDS-CAS mobile application and is subject to timely data syncs."]

                ]
            ]
        ]
