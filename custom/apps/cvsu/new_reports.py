from corehq.toggles import USER_CONFIGURABLE_REPORTS
from custom.apps.cvsu.new_sqldata import NewChildProtectionData, NewChildrenInHouseholdData, \
    NewChildProtectionDataTrend, NewChildrenInHouseholdDataTrend, NewCVSUActivityData, NewCVSUServicesData, \
    NewCVSUIncidentResolutionData, NewCVSUActivityDataTrend, NewCVSUServicesDataTrend, \
    NewCVSUIncidentResolutionDataTrend
from custom.apps.cvsu.reports import ChildProtectionReport, ChildProtectionReportTrend, CVSUPerformanceReport, \
    CVSUPerformanceReportTrend
from custom.apps.cvsu.sqldata import CVSUServicesDataTrend, CVSUIncidentResolutionDataTrend
from dimagi.utils.decorators.memoized import memoized


class NewChildProtectionReport(ChildProtectionReport):

    slug = 'new_child_protection_report'

    def show_in_navigation(cls, domain=None, project=None, user=None):
        return USER_CONFIGURABLE_REPORTS.enabled(user.username)

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            NewChildProtectionData(config=config),
            NewChildrenInHouseholdData(config=config)
        ]


class NewChildProtectionReportTrend(ChildProtectionReportTrend):

    slug = 'new_child_protection_report_trend'

    def show_in_navigation(cls, domain=None, project=None, user=None):
        return USER_CONFIGURABLE_REPORTS.enabled(user.username)

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            NewChildProtectionDataTrend(config=config),
            NewChildrenInHouseholdDataTrend(config=config)
        ]


class NewCVSUPerformanceReport(CVSUPerformanceReport):

    slug = 'new_cvsu_performance_report'

    def show_in_navigation(cls, domain=None, project=None, user=None):
        return USER_CONFIGURABLE_REPORTS.enabled(user.username)

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            NewCVSUActivityData(config=config),
            NewCVSUServicesData(config=config),
            NewCVSUIncidentResolutionData(config=config)
        ]


class NewCVSUPerformanceReportTrend(CVSUPerformanceReportTrend):

    slug = 'new_cvsu_performance_report_trend'

    def show_in_navigation(cls, domain=None, project=None, user=None):
        return USER_CONFIGURABLE_REPORTS.enabled(user.username)

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            NewCVSUActivityDataTrend(config=config),
            NewCVSUServicesDataTrend(config=config),
            NewCVSUIncidentResolutionDataTrend(config=config)
        ]
