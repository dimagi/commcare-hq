from django.conf.urls import patterns, url

urlpatterns = patterns('corehq.apps.dashboard.views',
    url(r'^$', 'dashboard_default', name="dashboard_default"),
)
