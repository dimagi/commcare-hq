from __future__ import absolute_import
from django.conf.urls import url

from corehq.apps.dashboard.views import (
    dashboard_default,
    dashboard_tile,
    DomainDashboardView,
)

urlpatterns = [
    url(r'^$', dashboard_default, name='dashboard_default'),
    url(r'^project/$', DomainDashboardView.as_view(), name=DomainDashboardView.urlname),
    url(r'^project/tile/(?P<slug>[\w-]+)/$', dashboard_tile, name='dashboard_tile'),
]
