from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    url(r'^$', 'bhoma.apps.phonelog.views.devices'),
)

