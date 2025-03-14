from django.urls import re_path as url

from corehq.apps.campaign.views import DashboardView, DashboardWidgetView

urlpatterns = [
    url(r'dashboard/', DashboardView.as_view(), name=DashboardView.urlname),
    url(r'dashboard_widget/', DashboardWidgetView.as_view(), name=DashboardWidgetView.urlname),

]
