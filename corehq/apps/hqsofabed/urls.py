from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.hqsofabed.views',
    (r'^$', 'formlist'),
)