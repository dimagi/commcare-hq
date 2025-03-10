from django.urls import re_path as url

from corehq.apps.campdash.views import (
    CampaignDashboardView,
    CampaignDashboardSettingsView,
    campaign_dashboard_data,
)

urlpatterns = [
    url(r'^$', CampaignDashboardView.as_view(), name=CampaignDashboardView.urlname),
    url(r'^settings/$', CampaignDashboardSettingsView.as_view(), name=CampaignDashboardSettingsView.urlname),
    url(r'^data/$', campaign_dashboard_data, name='campaign_dashboard_data'),
]
