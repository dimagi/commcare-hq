from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    (r'^requestlog/?$', 'requestlogger.views.demo'),    
    
)
