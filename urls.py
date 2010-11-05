from django.conf.urls.defaults import *

urlpatterns = patterns('',         
    url(r'^$', 'bhoma.apps.phonelog.views.devices'),
    url(r'^(?P<device>\w+)/$', 'bhoma.apps.phonelog.views.device_log'),                      
)

