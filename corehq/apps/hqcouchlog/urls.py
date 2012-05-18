from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.hqcouchlog.views',
    (r'^fail/$', 'fail'),
)