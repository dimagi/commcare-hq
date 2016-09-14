from django.conf.urls import patterns, url

from corehq.apps.loadtestendpoints.views import noop, saving

urlpatterns = patterns(
    'corehq.apps.loadtestendpoints.views',
    url(r'^noop/$', noop),
    url(r'^saving/$', saving),
)
