from django.conf.urls.defaults import *


urlpatterns = patterns('',                       
    url(r'^ota_restore/?$', 'ota_restore.views.restore'),
)
