from __future__ import unicode_literals, absolute_import

from custom.icds_reports.models import AggAwcMonthly

class IncentiveReport(object):

    def __init__(self, block, month):
        self.block = block
        self.month = month
        
    def get_excel_data(self):
        data = AggAwcMonthly.objects.filter(aggregation_level=5, month=self.month, block_id=self.block).values('state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name', 'aww_name', 'contact_phone_number', 'wer_weighed', 'wer_eligible', 'awc_num_open')

        headers = ['State', 'District', 'Block', 'Supervisor', 'AWC', 'AWW Name', 'AWW Contact Number', 'Home Visits Conducted', 'Number of Days AWC was Open', 'Weighing Efficiency', 'Eligible for Incentive']

        excel_rows = []
        excel_rows.append(headers)
        for row in data:
            excel_rows.append(row['state_name'], row['district_name'], row['block_name'], row['supervisor_name'], row['awc_name'], row['aww_name'], row['contact_phone_number'], '0', row['awc_num_open'], row['wer_weighed'] / row['wer_eligible'], 'Yes')

        return [['Incentive Report', excel_rows]]

