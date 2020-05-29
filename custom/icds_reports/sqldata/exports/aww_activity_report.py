from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.models.aggregate import AggregateInactiveAWW
from custom.icds_reports.utils import india_now, DATA_NOT_ENTERED


class AwwActivityExport(object):
    title = 'AWW Activity Report'

    def __init__(self, config, loc_level=0, beta=False):
        self.config = config
        self.loc_level = loc_level
        self.beta = beta

    def get_excel_data(self, location):

        def _format_infrastructure_data(data):
            return data if data is not None else DATA_NOT_ENTERED

        def _format_date(data):
            return data.strftime("%d-%m-%Y") if data is not DATA_NOT_ENTERED else data

        filters = {}

        if self.loc_level == 4:
            filters['supervisor_id'] = location
            order_by = ('awc_name',)
        elif self.loc_level == 3:
            filters['block_id'] = location
            order_by = ('supervisor_name', 'awc_name')
        elif self.loc_level == 2:
            filters['district_id'] = location
            order_by = ('block_name', 'supervisor_name', 'awc_name')
        elif self.loc_level == 1:
            filters['state_id'] = location
            order_by = ('district_name', 'block_name', 'supervisor_name', 'awc_name')
        else:
            order_by = ('state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name')

        query_set = AggregateInactiveAWW.objects.filter(**filters).order_by(*order_by)

        data = query_set.values('state_name', 'district_name', 'block_name', 'supervisor_name', 'awc_name',
                                'awc_site_code', 'first_submission', 'last_submission', 'no_of_days_since_start',
                                'no_of_days_inactive')

        headers = ['State', 'District', 'Block', 'Supervisor name', 'Awc Name', 'AWC site code',
                   'AWC launch date', 'Last submission date', 'Days since start', 'Days inactive']

        excel_rows = [headers]

        for row in data:
            row_data = [
                row['state_name'],
                row['district_name'],
                row['block_name'],
                row['supervisor_name'],
                row['awc_name'],
                row['awc_site_code'],
                _format_date(_format_infrastructure_data(row['first_submission'])),
                _format_date(_format_infrastructure_data(row['last_submission'])),
                _format_infrastructure_data(row['no_of_days_since_start']),
                _format_infrastructure_data(row['no_of_days_inactive'])
            ]

            excel_rows.append(row_data)
        filters = [['Generated at', india_now()]]
        if location:
            locs = SQLLocation.objects.get(location_id=location).get_ancestors(include_self=True)
            for loc in locs:
                filters.append([loc.location_type.name.title(), loc.name])

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
