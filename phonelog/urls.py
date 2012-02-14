from django.conf.urls.defaults import *

urlpatterns = patterns('',         
    url(r'^$', 'phonelog.views.devices'),
    url(r'^(?P<device>\w+)/$', 'phonelog.views.device_log'),                      
    url(r'^(?P<device>\w+)/raw/$', 'phonelog.views.device_log_raw'),                      
)

