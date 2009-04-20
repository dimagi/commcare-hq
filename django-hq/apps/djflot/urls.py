from django.conf.urls.defaults import *

urlpatterns = patterns('',    
        (r'^inspector/(?P<table_name>.*)/$', 'djflot.views.inspector'),
        (r'^showgraph/$', 'djflot.views.show_rawgraphs'),
        (r'^showgraph/(?P<graph_id>\d+)/$', 'djflot.views.view_rawgraph'),
        (r'^showgraph/all/$', 'djflot.views.show_multi'),
)
