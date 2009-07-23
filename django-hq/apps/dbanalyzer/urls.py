from django.conf.urls.defaults import *

urlpatterns = patterns('',    
        (r'^inspector/(?P<table_name>.*)/$', 'dbanalyzer.views.inspector'),
        (r'^showgraph/$', 'dbanalyzer.views.show_allgraphs'),
        (r'^showgraph/(?P<graph_id>\d+)/$', 'dbanalyzer.views.view_graph'),
        (r'^showgraph/all/$', 'dbanalyzer.views.show_multi'),
        (r'^groups/$', 'dbanalyzer.views.view_groups'),
        (r'^groups/(?P<group_id>\d+)/$', 'dbanalyzer.views.view_group'),
)
