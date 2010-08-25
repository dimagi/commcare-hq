from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    (r'^requestlog/?$', 'corehq.apps.requestlogger.views.list'),    
    (r'^requestlog/demo/?$', 'corehq.apps.requestlogger.views.demo'),    
    
)
