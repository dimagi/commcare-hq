from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    (r'^requestlog/?$', 'requestlogger.views.list'),    
    (r'^requestlog/demo/?$', 'requestlogger.views.demo'),    
    
)
