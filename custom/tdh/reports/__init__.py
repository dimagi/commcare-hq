from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from dimagi.utils.decorators.memoized import memoized
from custom.tdh.filters import TDHDateSpanFilter


class TDHReport(ProjectReportParametersMixin, CustomProjectReport, DatespanMixin, GenericTabularReport):
    emailable = False
    exportable = True
    export_format_override = 'csv'
    report_template_path = "reports/async/tabular.html"
    fields = [ExpandedMobileWorkerFilter, TDHDateSpanFilter]

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            startdate=self.datespan.startdate,
            enddate=self.datespan.enddate,
        )
        return config

    @property
    def data_provider(self):
        return None

    @property
    def headers(self):
        return self.data_provider.headers

    @property
    def rows(self):
        return self.data_provider.rows