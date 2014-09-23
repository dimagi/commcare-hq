from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin


class MotherTTCReport(ProjectReportParametersMixin, DatespanMixin, GenericTabularReport, CustomProjectReport):
    report_title = 'Mother Report'
    name = 'Mother Report'
    slug = 'mother_report'
    fields = [DatespanFilter,]