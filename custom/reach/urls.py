from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url, include

from custom.reach.views import DashboardView

dashboardurls = [
    url('^', DashboardView.as_view(), name='reach_dashboard'),
]

urlpatterns = [
    url(r'^reach_dashboard/', include(dashboardurls)),
]