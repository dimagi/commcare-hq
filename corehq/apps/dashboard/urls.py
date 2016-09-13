from django.conf.urls import url

from corehq.apps.dashboard.views import dashboard_default, DomainDashboardView

urlpatterns = [
    url(r'^$', dashboard_default, name='dashboard_default'),
    url(r'^project/$', DomainDashboardView.as_view(),
        name=DomainDashboardView.urlname),
]
