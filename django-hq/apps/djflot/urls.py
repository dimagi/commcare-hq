from django.conf.urls.defaults import *

urlpatterns = patterns('',    
        (r'^inspector/(?P<table_name>.*)/$', 'djflot.views.inspector'),
)
