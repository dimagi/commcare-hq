from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from custom.up_nrhm.filters import DrillDownOptionFilter
from custom.up_nrhm.sql_data import ASHAFunctionalityChecklistData


class ASHAFunctionalityChecklistReport(GenericTabularReport, DatespanMixin, CustomProjectReport):
    fields = [DatespanFilter, DrillDownOptionFilter]
    name = "ASHA Functionality Checklist Report"
    slug = "asha_functionality_checklist_report"
    report_template_path = "up_nrhm/asha_functionality.html"
    show_all_rows = True
    default_rows = 20
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
        return ASHAFunctionalityChecklistData(config=self.report_config)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Sl. No.', sortable=False, sort_type="title-numeric"),
            DataTablesColumn('ASHA Name', sortable=False),
            DataTablesColumn('Date of last form submission', sortable=False),
        )

    @property
    def rows(self):
        return [[index + 1, '<text id=%s>%s</text>' % (v['doc_id'], v['hv_asha_name']),
                 v['date']] for index, v in enumerate(self.model.data.values())]
