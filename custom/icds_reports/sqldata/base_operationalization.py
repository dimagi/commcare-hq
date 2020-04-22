from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.datatables import DataTablesHeader

from custom.icds_reports.models.aggregate import AggAwc
from custom.icds_reports.utils import ICDSMixin


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
            location_id = self.config['location_id']
            month = self.config['month']
            location_type = self.selected_location.location_type.name
            data = AggAwc.objects.get(f'{location_type}_id'=location_id, aggregation_level=self.aggregation_level, month=month).values('awc_num_open')
            return [
                [
                    'No. of AWCs',
                    self.awc_number,
                    data['awc_num_open'],
                    data['awc_num_open']
                ],
                [
                    'No. of Mini AWCs',
                    0,
                    0,
                    0
                ]
            ]
