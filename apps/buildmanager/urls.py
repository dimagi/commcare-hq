from django.conf.urls.defaults import *

urlpatterns = patterns('',                       
    (r'^projects/$', 'buildmanager.views.all_projects'),
    (r'^projects/(?P<project_id>\d+)/?$', 'buildmanager.views.show_project'),
    (r'^projects/(?P<project_id>\d+)/latest/?$', 'buildmanager.views.show_latest_build'),
    url(r'^projects/(?P<project_id>\d+)/latest/(?P<filename>.*)$', 'buildmanager.views.get_latest_buildfile',name='get_latest_buildfile'),
    (r'^builds/?$', 'buildmanager.views.all_builds'),
    url(r'^builds/xforms/(?P<id>\d+)/?$', 'buildmanager.views.get_build_xform', name="get_build_xform"),    
    (r'^builds/(?P<build_id>\d+)/release/?$', 'buildmanager.views.release'),    
    url(r'^builds/(?P<project_id>\d+)/(?P<build_number>\d+)/(?P<filename>.*)', 'buildmanager.views.get_buildfile',name='get_buildfile'),
    (r'^builds/show/(?P<build_id>\d+)', 'buildmanager.views.show_build'),    
    (r'^builds/new$', 'buildmanager.views.new_build'),
)
