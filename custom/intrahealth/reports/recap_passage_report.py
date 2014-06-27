from corehq.apps.locations.models import Location
from corehq.apps.reports.datatables import DataTablesColumnGroup, DataTablesHeader
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.sqlreport import calculate_total_row
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from custom.intrahealth.filters import RecapPassageLocationFilter
from custom.intrahealth.reports import IntraHealthLocationMixin, IntraHealthReportConfigMixin
from custom.intrahealth.sqldata import RecapPassageData


class RecapPassageReport(DatespanMixin, GenericTabularReport, CustomProjectReport, IntraHealthLocationMixin, IntraHealthReportConfigMixin):
    name = "Recap Passage"
    slug = 'recap_passage'
    report_title = "Recap Passage"
    fields = [DatespanFilter, RecapPassageLocationFilter]

    def config_update(self, config):
        if self.request.GET.get('location_id', ''):
            if self.location.location_type.lower() == 'pps':
                config.update(dict(PPS_name=self.location.name))

    @property
    def model(self):
        return RecapPassageData(config=self.report_config)

    @property
    def headers(self):
        header = DataTablesHeader()
        for column in self.model.columns:
            header.add_column(DataTablesColumnGroup('', column.data_tables_column))
        return header

    @property
    def rows(self):
        def _format_pps_restant(row):
            if row[-1] < 0:
               row[-1] = 0
            return row

        rows = [ _format_pps_restant(row) for row in self.model.rows]
        self.total_row = list(calculate_total_row(rows))
        return rows