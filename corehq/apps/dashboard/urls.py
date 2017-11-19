from __future__ import absolute_import
from django.conf.urls import url

from corehq.apps.dashboard.views import (
    dashboard_default,
    dashboard_tile,
    KODomainDashboardView,
)

urlpatterns = [
    url(r'^$', dashboard_default, name='dashboard_default'),
    url(r'^ko-project/$', KODomainDashboardView.as_view(), name=KODomainDashboardView.urlname),
    url(r'^ko-project/tile/(?P<slug>[\w-]+)/$', dashboard_tile, name='dashboard_tile'),
]
