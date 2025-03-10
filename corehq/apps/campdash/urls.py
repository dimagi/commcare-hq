from django.urls import re_path as url

from corehq.apps.campdash.views import (
    CampaignDashboardView,
    MapReportView,
)

urlpatterns = [
    url(
        r'^$',
        CampaignDashboardView.as_view(),
        name=CampaignDashboardView.urlname,
    ),
    url(
        r'^map_report/(?P<subreport_slug>[\w-]+)/$',
        MapReportView.as_view(),
        name='campaign_map_report',
    ),
]
