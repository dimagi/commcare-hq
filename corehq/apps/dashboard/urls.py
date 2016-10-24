from django.conf.urls import patterns, url

from corehq.apps.dashboard.views import dashboard_default, DomainDashboardView, NewUserDashboardView

urlpatterns = patterns('corehq.apps.dashboard.views',
    url(r'^$', dashboard_default, name='dashboard_default'),
    url(r'^project/$', DomainDashboardView.as_view(), name=DomainDashboardView.urlname),
    url(r'^apps/$', NewUserDashboardView.as_view(), name=NewUserDashboardView.urlname),
)
