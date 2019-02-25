from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url, include

from custom.aaa.views import (
    AggregationScriptPage,
    LocationFilterAPI,
    ProgramOverviewReport,
    ProgramOverviewReportAPI,
    UnifiedBeneficiaryReport,
    UnifiedBeneficiaryReportAPI
)

dashboardurls = [
    url('^program_overview/', ProgramOverviewReport.as_view(), name='program_overview'),
    url('^unified_beneficiary/', UnifiedBeneficiaryReport.as_view(), name='unified_beneficiary'),
]

dataurls = [
    url('^program_overview/', ProgramOverviewReportAPI.as_view(), name='program_overview_api'),
    url('^unified_beneficiary/', UnifiedBeneficiaryReportAPI.as_view(), name='unified_beneficiary_api'),
    url('^location_api/', LocationFilterAPI.as_view(), name='location_api'),
    url(r'^aggregate/', AggregationScriptPage.as_view(), name=AggregationScriptPage.urlname),
]

urlpatterns = [
    url(r'^aaa_dashboard/', include(dashboardurls)),
    url(r'^aaa_dashboard_data/', include(dataurls)),
]
