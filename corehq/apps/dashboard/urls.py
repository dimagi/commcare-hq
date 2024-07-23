from django.urls import re_path as url

from corehq.apps.dashboard.views import (
    DomainDashboardView,
    dashboard_tile,
    dashboard_tile_total,
)

urlpatterns = [
    url(r'^$', DomainDashboardView.as_view(), name='dashboard_default'),
    url(r'^project/$', DomainDashboardView.as_view(), name=DomainDashboardView.urlname),
    url(r'^project/tile/(?P<slug>[\w-]+)/$', dashboard_tile, name='dashboard_tile'),
    url(r'^project/tile/(?P<slug>[\w-]+)/total/$', dashboard_tile_total, name='dashboard_tile_total'),
]
