from django.conf.urls import *

urlpatterns = patterns('corehq.apps.hqcouchlog.views',
    (r'^fail/$', 'fail'),
)