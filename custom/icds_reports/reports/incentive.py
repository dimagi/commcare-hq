from __future__ import unicode_literals, absolute_import, division

from custom.icds_reports.models.aggregate import AWWIncentiveReport
from custom.icds_reports.utils import india_now, DATA_NOT_ENTERED


class IncentiveReport(object):

    def __init__(self, location, month, aggregation_level, beta):
        self.location = location
        self.month = month
        self.aggregation_level = aggregation_level
        self.beta = beta

    def get_excel_data(self):

        def _format_infrastructure_data(data):
            return data if data else DATA_NOT_ENTERED

        if self.aggregation_level == 1:
            data = AWWIncentiveReport.objects.filter(
                month=self.month, state_id=self.location
            ).order_by('-district_name', '-block_name', '-supervisor_name')
        elif self.aggregation_level == 2:
            data = AWWIncentiveReport.objects.filter(
                month=self.month, district_id=self.location
            ).order_by('-block_name', '-supervisor_name')
        else:
            data = AWWIncentiveReport.objects.filter(
                month=self.month, block_id=self.location
            ).order_by('-supervisor_name', 'awc_name')
        data = data.values(
            'state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name', 'aww_name',
            'contact_phone_number', 'wer_weighed', 'wer_eligible', 'awc_num_open', 'valid_visits',
            'visit_denominator', 'is_launched', 'awh_eligible', 'incentive_eligible'
        )

        if self.beta:
            headers = [
                'State', 'District', 'Block', 'Supervisor', 'AWC', 'AWW Name', 'AWW Contact Number',
                'Home Visits Conducted', 'Weighing Efficiency', 'AWW Eligible for Incentive',
                'Number of Days AWC was Open', 'AWH Eligible for Incentive'
            ]
        else:
            headers = [
                'State', 'District', 'Block', 'Supervisor', 'AWC', 'AWW Name', 'AWW Contact Number',
                'Home Visits Conducted', 'Number of Days AWC was Open', 'Weighing Efficiency',
                'Eligible for Incentive'
            ]

        excel_rows = [headers]

        for row in data:
            row_data = [
                row['state_name'],
                row['district_name'],
                row['block_name'],
                row['supervisor_name'],
                row['awc_name'],
            ]

            # AWC not launched
            if row['is_launched'] != 'yes':
                AWC_NOT_LAUNCHED = 'AWC not launched'
                row_data.extend([
                    AWC_NOT_LAUNCHED,
                    AWC_NOT_LAUNCHED,
                    AWC_NOT_LAUNCHED,
                    AWC_NOT_LAUNCHED,
                    AWC_NOT_LAUNCHED,
                    AWC_NOT_LAUNCHED
                ])
                if self.beta:
                    row_data.append(AWC_NOT_LAUNCHED)
            else:
                home_visit_percent = row['valid_visits'] / row['visit_denominator'] if \
                    row['visit_denominator'] else 1
                weighing_efficiency_percent = row['wer_weighed'] / row['wer_eligible'] if \
                    row['wer_eligible'] else 1
                if home_visit_percent > 1:
                    home_visit_percent = 1
                home_visit_conducted = '{:.2%}'.format(home_visit_percent)
                if row['awc_num_open'] is None:
                    num_open = DATA_NOT_ENTERED
                else:
                    num_open = row['awc_num_open']
                weighing_efficiency = '{:.2%}'.format(weighing_efficiency_percent)
                eligible_for_incentive = row['incentive_eligible']
                no_visits = row['valid_visits'] == 0 and row['visit_denominator'] == 0
                no_weights = row['wer_eligible'] == 0
                if no_visits:
                    home_visit_conducted = "No expected home visits"
                if no_weights:
                    weighing_efficiency = "No expected weight measurement"

                if self.beta:
                    awh_eligible = row['awh_eligible']
                    row_data.extend([
                        _format_infrastructure_data(row['aww_name']),
                        _format_infrastructure_data(row['contact_phone_number']),
                        home_visit_conducted,
                        weighing_efficiency,
                        eligible_for_incentive,
                        num_open,
                        awh_eligible_for_incentive
                    ])
                else:
                    row_data.extend([
                        _format_infrastructure_data(row['aww_name']),
                        _format_infrastructure_data(row['contact_phone_number']),
                        home_visit_conducted,
                        num_open,
                        weighing_efficiency,
                        eligible_for_incentive
                    ])

            excel_rows.append(row_data)

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
                    ['Disclaimer', "The information in the report is based on the self-reported data entered by "
                                   "the Anganwadi Worker in ICDS-CAS mobile application and is subject to timely "
                                   "data syncs."]
                ]
            ]
        ]
