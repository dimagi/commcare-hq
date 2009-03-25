from django.conf.urls.defaults import *


urlpatterns = patterns('',
    url(r'^edgetype/all/$', 'modelrelationship.views.all_edgetypes', name='view_all_edgetypes'),
    url(r'^edgetype/new/$', 'modelrelationship.views.new_edgetype', name='new_edgetype'),
    url(r'^edgetype/(?P<edgetype_id>\d+)$', 'modelrelationship.views.single_edgetype', name='view_single_edgetype'),
    
    url(r'^edgetype/(?P<edgetype_id>\d+)/newedge$', 'modelrelationship.views.new_edge', name='new_edge'),
    
    url(r'^edge/all/$', 'modelrelationship.views.all_edges', name='view_all_edges'),
    url(r'^edge/(?P<edge_id>\d+)/$', 'modelrelationship.views.view_single_edge', name='view_single_edge'),
)
