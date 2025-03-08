from django.urls import re_path as url

from corehq.apps.campdash.views import CampaignDashboardView

urlpatterns = [
    url(
        r'^$',
        CampaignDashboardView.as_view(),
        name=CampaignDashboardView.urlname,
    ),
]
