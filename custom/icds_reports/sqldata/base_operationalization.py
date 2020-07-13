from datetime import date


from custom.icds_reports.utils import ICDSMixin
from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.datatables import DataTablesHeader
from custom.icds_reports.models.aggregate import AggAwc
from custom.icds_reports.utils import get_location_filter

class BaseOperationalization(ICDSMixin):

    title = 'c. Status of operationalization of AWCs'
    slug = 'operationalization'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('', sortable=False),
            DataTablesColumn('Sanctioned', sortable=False),
            DataTablesColumn('Functioning', sortable=False),
            DataTablesColumn('Reporting', sortable=False)
        )

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            return [
                [
                    'No. of AWCs',
                    self.awc_number,
                    data['owner_id'],
                    data['owner_id']
                ],
                [
                    'No. of Mini AWCs',
                    0,
                    0,
                    0
                ]
            ]


class BaseOperationalizationBeta(ICDSMixin):

    title = 'c. Status of operationalization of AWCs'
    slug = 'operationalization'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('', sortable=False),
            DataTablesColumn('Sanctioned', sortable=False),
            DataTablesColumn('Functioning', sortable=False),
            DataTablesColumn('Reporting', sortable=False)
        )

    @property
    def rows(self):

        if self.config['location_id']:
            filters = get_location_filter(self.config['location_id'], self.config['domain'])

            if filters.get('aggregation_level')>1:
                filters['aggregation_level'] -= 1

            filters['month'] = date(self.config['year'], self.config['month'], 1)
            print(filters)
            awc_data = AggAwc.objects.filter(**filters).values(
                'num_awcs',
                'num_launched_awcs',
                'awc_num_open').order_by('month').first()

            print(AggAwc.objects.filter(**filters).values(
                'num_awcs',
                'num_launched_awcs',
                'awc_num_open').order_by('month').query)

            return [
                [
                    'No. of AWCs',
                    awc_data.num_awcs if awc_data else None,
                    awc_data.num_launched_awcs if awc_data else None,
                    awc_data.awc_num_open if awc_data else None
                ],
                [
                    'No. of Mini AWCs',
                    0,
                    0,
                    0
                ]
            ]
