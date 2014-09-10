from django.conf.urls import patterns, url
from corehq.apps.dashboard.views import *

urlpatterns = patterns('corehq.apps.dashboard.views',
    url(r'^$', 'dashboard_default', name="dashboard_default"),
    url(r'^welcome/$', NewUserDashboardView.as_view(),
        name=NewUserDashboardView.urlname),
)
