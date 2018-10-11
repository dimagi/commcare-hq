from __future__ import unicode_literals, absolute_import


from custom.icds_reports.models.aggregate import AWWIncentiveReport
from custom.icds_reports.utils import india_now

class IncentiveReport(object):

    def __init__(self, block, month):
        self.block = block
        self.month = month

    def get_excel_data(self):
        data = AWWIncentiveReport.objects.filter(aggregation_level=5, month=self.month, block_id=self.block).values('state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name', 'aww_name', 'contact_phone_number', 'wer_weighed', 'wer_eligible', 'awc_num_open', 'valid_visits', 'expected_visits')

        headers = ['State', 'District', 'Block', 'Supervisor', 'AWC', 'AWW Name', 'AWW Contact Number', 'Home Visits Conducted', 'Number of Days AWC was Open', 'Weighing Efficiency', 'Eligible for Incentive']

        home_visit_percent = row['valid_visits'] / row['expected_visits']
        weighing_efficiency = row['wer_weighed'] / row['wer_eligible']

        excel_rows = []
        excel_rows.append(headers)
        for row in data:
            excel_rows.append(row['state_name'],
                              row['district_name'],
                              row['block_name'],
                              row['supervisor_name'],
                              row['awc_name'], row['aww_name'],
                              row['contact_phone_number'],
                              home_visit_percent,
                              row['awc_num_open'],
                              weighing_efficiency,
                              'Yes' if weighing_efficiency > 0.6 and home_visit_percent > 0.6 else 'No')

        return [
            [
                'Incentive Report',
                excel_rows
            ],
            [
                'Export Info',
                [
                    ['Generated at', india_now()],
                    ['Grouped By', 'AWC'],
                    ['Month', self.month.month],
                    ['Year', self.month.year]
                    ['Disclaimer', "The information in the report is based on the self-reported data entered by the Anganwadi Worker in ICDS-CAS mobile application and is subject to timely data syncs."]

                ]
            ]
        ]
