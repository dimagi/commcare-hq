from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin, CustomProjectReport


class TTCReport(ProjectReportParametersMixin, DatespanMixin, GenericTabularReport, CustomProjectReport):
    fields = [DatespanFilter,]