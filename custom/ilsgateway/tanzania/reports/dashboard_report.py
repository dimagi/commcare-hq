from custom.ilsgateway.filters import ProgramFilter, MonthAndQuarterFilter
from custom.ilsgateway.tanzania import MultiReport
from custom.ilsgateway.tanzania.reports.facility_details import InventoryHistoryData, RegistrationData, \
    RandRHistory, Notes, RecentMessages
from custom.ilsgateway.tanzania.reports.mixins import RandRSubmissionData, DistrictSummaryData, \
    SohSubmissionData, DeliverySubmissionData, ProductAvailabilitySummary
from custom.ilsgateway.tanzania.reports.stock_on_hand import StockOnHandReport
from custom.ilsgateway.tanzania.reports.utils import make_url
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import YearFilter
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _


class DashboardReport(MultiReport):
    slug = 'ils_dashboard_report'
    name = "Dashboard report"

    @property
    def title(self):
        title = _("Dashboard report {0}".format(self.title_month))
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            return "{0} ({1}) Group {2}".format(self.location.name,
                                                self.location.site_code,
                                                self.location.metadata.get('group', '---'))
        return title

    @property
    def fields(self):
        fields = [AsyncLocationFilter, MonthAndQuarterFilter, YearFilter, ProgramFilter]
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            fields = []
        return fields

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        if self.location:
            if self.location.location_type.name.upper() == 'FACILITY':
                self.use_datatables = True
                return [
                    InventoryHistoryData(config=config),
                    RandRHistory(config=config),
                    Notes(config=config),
                    RecentMessages(config=config),
                    RegistrationData(config=dict(loc_type='FACILITY', **config), css_class='row_chart_all'),
                    RegistrationData(config=dict(loc_type='DISTRICT', **config), css_class='row_chart_all'),
                    RegistrationData(config=dict(loc_type='REGION', **config), css_class='row_chart_all')
                ]
            else:
                self.use_datatables = False
                return [
                    RandRSubmissionData(config=config),
                    DistrictSummaryData(config=config),
                    SohSubmissionData(config=config),
                    DeliverySubmissionData(config=config),
                    ProductAvailabilitySummary(config=config, css_class='row_chart_all')
                ]
        else:
            return []

    @property
    def report_facilities_url(self):
        config = self.report_config
        return make_url(
            StockOnHandReport,
            self.domain,
            '?location_id=%s&month=%s&year=%s&filter_by_program=%s',
            (config['location_id'], config['month'], config['year'], config['program'])
        )
