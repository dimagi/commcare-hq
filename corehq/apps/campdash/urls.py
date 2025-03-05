from django.urls import re_path as url

from corehq.apps.campdash.views import (
    CampaignDashboardView,
    campaign_dashboard_data,
)

urlpatterns = [
    url(r'^$', CampaignDashboardView.as_view(), name=CampaignDashboardView.urlname),
    url(r'^data/$', campaign_dashboard_data, name='campaign_dashboard_data'),
]
