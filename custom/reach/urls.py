from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url, include

from custom.reach.views import ProgramOverviewReport, UnifiedBeneficiaryReport, ProgramOverviewReportAPI

dashboardurls = [
    url('^program_overview/', ProgramOverviewReport.as_view(), name='program_overview'),
    url('^unified_beneficiary/', UnifiedBeneficiaryReport.as_view(), name='unified_beneficiary'),
]

dataurls = [
    url('^program_overview/', ProgramOverviewReportAPI.as_view(), name='program_overview_api'),
]

urlpatterns = [
    url(r'^reach_dashboard/', include(dashboardurls)),
    url(r'^reach_dashboard_data/', include(dataurls)),
]
