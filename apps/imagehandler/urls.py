from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    (r'^imagehandler/?$', 'imagehandler.views.home'),    
    # (r'^requestlog/demo/?$', 'requestlogger.views.demo'),        
)
