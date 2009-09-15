from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^xforms/$', 'xformmanager.views.register_xform'),
    (r'^xforms/register/$', 'xformmanager.views.register_xform'),
    (r'^xforms/reregister/(?P<domain_name>.*)/?$', 'xformmanager.views.reregister_xform'),
    (r'^xforms/remove/(?P<form_id>\d+)/?$', 'xformmanager.views.remove_xform'),
    (r'^xforms/show/(?P<formdef_id>\d+)/?$', 'xformmanager.views.single_xform'),
    url(r'^xforms/show/(?P<formdef_id>\d+)/(?P<instance_id>\d+)/?$', 'xformmanager.views.single_instance', name="single_instance"),
    (r'^xforms/show/(?P<formdef_id>\d+)/(?P<instance_id>\d+)/csv/?$', 'xformmanager.views.single_instance_csv'),
    url(r'^xforms/data/(?P<formdef_id>\d+)/delete/?$', 'xformmanager.views.delete_data', name="delete_data"),
    (r'^xforms/data/(?P<formdef_id>\d+)/?$', 'xformmanager.views.data'),
    (r'^xforms/data/(?P<formdef_id>\d+)/csv/?$', 'xformmanager.views.export_csv'),
    (r'^xforms/data/(?P<formdef_id>\d+)/xml/?$', 'xformmanager.views.export_xml'),
    (r'^xforms/(?P<formdef_id>\d+)/submit/?$', 'xformmanager.views.submit_data'),
    (r'', include('xformmanager.api_.urls')),
)
