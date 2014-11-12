from datetime import timedelta
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter
from corehq.apps.reports.sqlreport import SqlTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from couchexport.models import Format
from custom.tdh.filters import TDHDateSpanFilter

UNNECESSARY_FIELDS = ['doc_type', 'numerator', 'base_doc', 'save_direct_to_sql', 'domain']


class TDHReport(SqlTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    use_datatables = True
    emailable = False
    exportable = True
    export_format_override = Format.UNZIPPED_CSV
    fields = [ExpandedMobileWorkerFilter, TDHDateSpanFilter]
    fix_left_col = True

    @property
    def report_config(self):
        emw = [u.user_id for u in ExpandedMobileWorkerFilter.pull_users_and_groups(
            self.domain, self.request, True, True).combined_users]
        if self.datespan.enddate - timedelta(days=30) > self.datespan.startdate:
            self.datespan.startdate = self.datespan.enddate - timedelta(days=30)
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
        return dict(num=3, width=350)

    @property
    def export_table(self):
        from custom.tdh.reports.child_consultation_history import ChildConsultationHistoryReport, \
            CompleteChildConsultationHistoryReport
        from custom.tdh.reports.infant_consultation_history import InfantConsultationHistoryReport, \
            CompleteInfantConsultationHistoryReport
        from custom.tdh.reports.newborn_consultation_history import NewbornConsultationHistoryReport, \
            CompleteNewbornConsultationHistoryReport

        if self.request_params['detailed'] and not isinstance(self, (
                CompleteNewbornConsultationHistoryReport, CompleteInfantConsultationHistoryReport,
                CompleteChildConsultationHistoryReport)):
            if isinstance(self, NewbornConsultationHistoryReport):
                return CompleteNewbornConsultationHistoryReport(
                    request=self.request, domain=self.domain).export_table
            elif isinstance(self, InfantConsultationHistoryReport):
                return CompleteInfantConsultationHistoryReport(
                    request=self.request, domain=self.domain).export_table
            elif isinstance(self, ChildConsultationHistoryReport):
                return CompleteChildConsultationHistoryReport(
                    request=self.request, domain=self.domain).export_table

        return [self._export_table(self.report_context['report_table']['headers'],
                                   self.report_context['report_table']['rows'])]

    def _export_table(self, headers, formatted_rows):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        replace = ''

        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace
        table.extend(rows)

        return ['', table]
