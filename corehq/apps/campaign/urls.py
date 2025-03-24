from django.urls import re_path as url

from corehq.apps.campaign.views import (
    DashboardView,
    PaginatedCasesWithGPSView,
)

urlpatterns = [
    url(r'dashboard/', DashboardView.as_view(), name=DashboardView.urlname),
    url(r'^api/cases_with_gps/$', PaginatedCasesWithGPSView.as_view(),
        name=PaginatedCasesWithGPSView.urlname),
]
