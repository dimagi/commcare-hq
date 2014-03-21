from django.conf.urls import patterns, url

urlpatterns = patterns(
    'corehq.apps.loadtestendpoints.views',
    url(r'^noop/$', 'noop'),
    url(r'^saving/$', 'saving'),
)
