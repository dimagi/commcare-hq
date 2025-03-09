from django.urls import re_path as url

from corehq.apps.campaign.views import DashboardView

urlpatterns = [
    url(r'dashboard/', DashboardView.as_view(), name=DashboardView.urlname),
]
