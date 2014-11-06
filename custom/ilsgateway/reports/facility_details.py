from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from custom.ilsgateway.reports.base_report import MultiReport
from dimagi.utils.decorators.memoized import memoized


class FacilityDetailsReport(MultiReport):

    title = "Dashboard report"
    fields = [AsyncLocationFilter, MonthFilter, YearFilter]
    name = "Dashboard report"
    slug = 'ils_dashboard_report'

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return []