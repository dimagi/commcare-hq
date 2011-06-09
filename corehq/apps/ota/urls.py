from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    url(r'^restore/$', 'corehq.apps.ota.views.restore'),
)

