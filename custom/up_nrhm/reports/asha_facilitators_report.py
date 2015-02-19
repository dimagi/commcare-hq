from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.util import format_datatables_data
from custom.up_nrhm.filters import DrillDownOptionFilter
from custom.up_nrhm.sql_data import ASHAFacilitatorsData


class ASHAFacilitatorsReport(GenericTabularReport, DatespanMixin, CustomProjectReport):
    name = "ASHA Facilitators Report"
    slug = "asha_facilitators_report"
    no_value = '--'

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'startdate': self.datespan.startdate,
            'enddate': self.datespan.enddate,
            'af': self.request.GET.get('hierarchy_af'),
        }

    @property
    def model(self):
        return ASHAFacilitatorsData(config=self.report_config)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('', sortable=False),
            DataTablesColumn('Total no. of ASHAs functional', sortable=False),
            DataTablesColumn('Total no. of ASHAs who did not report/not known', sortable=False),
            DataTablesColumn('Remarks', sortable=False),
        )

    @property
    def rows(self):
        def format_val(val):
            return self.no_value if val is None else val

        model = self.model
        model_data = model.data

        total = model.columns[0].get_raw_value(model_data)
        reporting = model.columns[1].get_raw_value(model_data)

        not_reporting = total - (reporting or 0)
        return ([[
            column.header,
            format_val(column.get_value(model_data)),
            format_datatables_data(not_reporting, not_reporting),
            ''
        ] for column in model.columns[2:]], format_val(total), format_val(reporting))
