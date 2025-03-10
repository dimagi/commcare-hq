from django.urls import re_path as url

from corehq.apps.campaign.views import DashboardView, MapReportView

urlpatterns = [
    url(r'dashboard/', DashboardView.as_view(), name=DashboardView.urlname),
    url(
        r'^map_report/(?P<subreport_slug>[\w-]+)/$',
        MapReportView.as_view(),
        name='campaign_map_report',
    ),
]
