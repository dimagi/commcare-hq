from django.conf.urls.defaults import *

urlpatterns = patterns('',    
        (r'^inspector/(?P<table_name>.*)/$', 'graphing.views.inspector'),
        (r'^showgraph/$', 'graphing.views.show_allgraphs'),
        (r'^showgraph/(?P<graph_id>\d+)/$', 'graphing.views.view_graph'),
        (r'^showgraph/all/$', 'graphing.views.show_multi'),
        (r'^chartgroups/$', 'graphing.views.view_groups'),
        (r'^chartgroups/(?P<group_id>\d+)/$', 'graphing.views.view_group'),
        (r'^charts/?$', 'graphing.views.domain_charts'),
        url(r'^charts/default/?$', 'graphing.views.summary_trend', name="summary_trend"),
        
)
