from django.conf.urls import patterns, url

from corehq.apps.hqcouchlog.views import fail

urlpatterns = patterns('corehq.apps.hqcouchlog.views',
    url(r'^fail/$', fail, name='fail'),
)
