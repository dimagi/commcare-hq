from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url, include

from custom.aaa.views import (
    AggregationScriptPage,
    LocationFilterAPI,
    ProgramOverviewReport,
    ProgramOverviewReportAPI,
    UnifiedBeneficiaryReport,
    UnifiedBeneficiaryReportAPI,
    UnifiedBeneficiaryDetailsReport,
    UnifiedBeneficiaryDetailsReportAPI,
)

dashboardurls = [
    url('^program_overview/', ProgramOverviewReport.as_view(), name='program_overview'),
    url('^unified_beneficiary/$', UnifiedBeneficiaryReport.as_view(), name='unified_beneficiary'),
    url(
        '^unified_beneficiary/(?P<details_type>[\w-]+)/(?P<beneficiary_id>[\w-]+)/$',
        UnifiedBeneficiaryDetailsReport.as_view(),
        name='unified_beneficiary_details'
    ),
]

dataurls = [
    url('^program_overview/', ProgramOverviewReportAPI.as_view(), name='program_overview_api'),
    url('^unified_beneficiary/', UnifiedBeneficiaryReportAPI.as_view(), name='unified_beneficiary_api'),
    url(
        '^unified_beneficiary_details/',
        UnifiedBeneficiaryDetailsReportAPI.as_view(),
        name='unified_beneficiary_details_api'
    ),
    url('^location_api/', LocationFilterAPI.as_view(), name='location_api'),
    url(r'^aggregate/', AggregationScriptPage.as_view(), name=AggregationScriptPage.urlname),
]

urlpatterns = [
    url(r'^aaa_dashboard/', include(dashboardurls)),
    url(r'^aaa_dashboard_data/', include(dataurls)),
]
