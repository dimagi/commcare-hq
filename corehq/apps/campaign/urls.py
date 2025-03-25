from django.urls import re_path as url

from corehq.apps.campaign.views import (
    DashboardView,
    DashboardWidgetView,
    PaginatedCasesWithGPSView,
    get_geo_case_properties_view,
)

urlpatterns = [
    url(r'dashboard/', DashboardView.as_view(), name=DashboardView.urlname),
    url(r'^api/cases_with_gps/$', PaginatedCasesWithGPSView.as_view(),
        name=PaginatedCasesWithGPSView.urlname),
    url(r'dashboard_widget/', DashboardWidgetView.as_view(), name=DashboardWidgetView.urlname),
    url(r'get_geo_case_properties/', get_geo_case_properties_view, name='get_geo_case_properties'),
]
