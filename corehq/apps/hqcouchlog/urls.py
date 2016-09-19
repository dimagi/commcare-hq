from django.conf.urls import *

from corehq.apps.hqcouchlog.views import fail

urlpatterns = patterns('corehq.apps.hqcouchlog.views',
    (r'^fail/$', fail),
)
