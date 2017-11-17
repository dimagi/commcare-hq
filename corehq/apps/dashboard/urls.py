from __future__ import absolute_import
from django.conf.urls import url

from corehq.apps.dashboard.views import dashboard_default, DomainDashboardView, KODomainDashboardView

urlpatterns = [
    url(r'^$', dashboard_default, name='dashboard_default'),
    url(r'^project/$', DomainDashboardView.as_view(), name=DomainDashboardView.urlname),
    url(r'^ko-project/$', KODomainDashboardView.as_view(), name=KODomainDashboardView.urlname),
]
