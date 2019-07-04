from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.utils import india_now, DATA_NOT_ENTERED
from custom.icds_reports.models.views import TakeHomeRationMonthly


class TakeHomeRationExport(object):
    title = 'Take Home Ration'

    def __init__(self, location, month, beta=False):
        self.location = location
        self.month = month
        self.beta = beta

    def get_excel_data(self):

        def _format_infrastructure_data(data):
            return data if data is not None else DATA_NOT_ENTERED

        filters = {"month": self.month, "aggregation_level": 5}

        all_order_by_columns = ('state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name')
        if not self.location:
            order_by = all_order_by_columns
        else:
            location = SQLLocation.by_location_id(self.location)
            location_type = location.location_type.name
            location_id_key = '{}_id'.format(location_type)

            filters[location_id_key] = self.location

            if location_type == 'state':
                order_by = all_order_by_columns[1:]

            elif location_type == 'district':
                order_by = all_order_by_columns[2:]

            elif location_type == 'block':
                order_by = all_order_by_columns[3:]

            elif location_type == 'supervisor':
                order_by = all_order_by_columns[4:]

        query_set = TakeHomeRationMonthly.objects.filter(**filters).order_by(*order_by)

        data = query_set.values('state_name', 'district_name', 'block_name',
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
