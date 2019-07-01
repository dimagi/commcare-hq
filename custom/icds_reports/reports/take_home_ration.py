from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.utils import india_now, DATA_NOT_ENTERED
from custom.icds_reports.models.views import TakeHomeRationMonthly


class TakeHomeRationExport(object):
    title = 'Take Home Ration'

    def __init__(self, location, month, loc_level=0, beta=False):
        self.location = location
        self.loc_level = loc_level
        self.month = month
        self.beta = beta

    def get_excel_data(self):

        def _format_infrastructure_data(data):
            return data if data is not None else DATA_NOT_ENTERED

        if self.loc_level == 4:
            data = TakeHomeRationMonthly.objects.filter(
                supervisor_id=self.location, month=self.month, aggregation_level=5
            ).order_by('awc_name')
        elif self.loc_level == 3:
            data = TakeHomeRationMonthly.objects.filter(
                block_id=self.location, month=self.month, aggregation_level=5
            ).order_by('supervisor_name', 'awc_name')
        elif self.loc_level == 2:
            data = TakeHomeRationMonthly.objects.filter(
                district_id=self.location, month=self.month, aggregation_level=5
            ).order_by('block_name', 'supervisor_name', 'awc_name')
        elif self.loc_level == 1:
            data = TakeHomeRationMonthly.objects.filter(
                state_id=self.location, month=self.month, aggregation_level=5
            ).order_by('district_name', 'block_name', 'supervisor_name', 'awc_name')
        else:
            data = TakeHomeRationMonthly.objects.filter(
                month=self.month, aggregation_level=5
            ).order_by('state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name')

        data = data.values('state_name', 'district_name', 'block_name',
                           'supervisor_name', 'awc_name', 'aww_name', 'contact_phone_number',
                           'is_launched', 'total_thr_candidates', 'thr_given_21_days',
                           'thr_distribution_image_count')

        headers = ['State', 'District', 'Block', 'Sector', 'Awc Name', 'AWW Name', 'AWW Phone No.',
                   'Total No. of Beneficiaries eligible for THR',
                   'Total No. of Beneficiaries received THR>21 days in given month',
                   'Total No of Pictures taken by AWW']

        excel_rows = [headers]

        for row in data:
            row_data = [
                row['state_name'],
                row['district_name'],
                row['block_name'],
                row['supervisor_name'],
                row['awc_name'],
            ]
            if row['is_launched'] != 'yes':
                AWC_NOT_LAUNCHED = 'AWC Not Launched'
                row_data.extend([
                    AWC_NOT_LAUNCHED,
                    AWC_NOT_LAUNCHED,
                    AWC_NOT_LAUNCHED,
                    AWC_NOT_LAUNCHED,
                    AWC_NOT_LAUNCHED,
                ])
            else:
                row_data.extend([
                    _format_infrastructure_data(row['aww_name']),
                    _format_infrastructure_data(row['contact_phone_number']),
                    _format_infrastructure_data(row['total_thr_candidates']),
                    _format_infrastructure_data(row['thr_given_21_days']),
                    _format_infrastructure_data(row['thr_distribution_image_count'])
                ])

            excel_rows.append(row_data)
        filters = [['Generated at', india_now()]]
        if self.location:
            locs = SQLLocation.objects.get(location_id=self.location).get_ancestors(include_self=True)
            for loc in locs:
                filters.append([loc.location_type.name.title(), loc.name])
        else:
            filters.append(['Location', 'National'])

        date = self.month
        filters.append(['Month', date.strftime("%B")])
        filters.append(['Year', date.year])

        return [
            [
                self.title,
                excel_rows
            ],
            [
                'Export Info',
                filters
            ]
        ]
