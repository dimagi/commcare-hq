from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin


class ChildTTCReport(ProjectReportParametersMixin, DatespanMixin, GenericTabularReport, CustomProjectReport):
    report_title = 'Child Report'
    name = 'Child Report'
    slug = 'child_report'
    fields = [DatespanFilter,]