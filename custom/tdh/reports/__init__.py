from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.reports.sqlreport import SqlTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from custom.tdh.filters import TDHDateSpanFilter

UNNECESSARY_FIELDS = ['doc_type', 'numerator', 'base_doc', 'save_direct_to_sql']


class TDHReport(SqlTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    use_datatables = True
    emailable = False
    exportable = True
    export_format_override = 'csv'
    fields = [ExpandedMobileWorkerFilter, TDHDateSpanFilter]
    fix_left_col = True

    @property
    def report_config(self):
        emw = [u.user_id for u in ExpandedMobileWorkerFilter.pull_users_and_groups(
            self.domain, self.request, True, True).combined_users]
        config = dict(
            domain=self.domain,
            startdate=self.datespan.startdate,
            enddate=self.datespan.enddate,
            emw=tuple(emw)
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

    @property
    def fixed_cols_spec(self):
        return dict(num=2, width=200)
