from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.builds.views',
    (r'^post/$', 'post'),
    (r'^(?P<version>.+)/(?P<build_number>\d+)/(?P<path>.+)$', "get"),
)