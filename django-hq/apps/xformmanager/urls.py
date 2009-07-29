from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^xforms/$', 'xformmanager.views.register_xform'),
    (r'^xforms/register/$', 'xformmanager.views.register_xform'),
    (r'^xforms/reregister/(?P<domain_name>.*)$', 'xformmanager.views.reregister_xform'),
    (r'^xforms/remove/(?P<form_id>\d+)/?$', 'xformmanager.views.remove_xform'),
    (r'^xforms/show/(?P<formdef_id>\d+)/?$', 'xformmanager.views.single_xform'),
    (r'^xforms/show/(?P<formdef_id>\d+)/(?P<instance_id>\d+)/?$', 'xformmanager.views.single_instance'),
    (r'^xforms/data/(?P<formdef_id>\d+)$', 'xformmanager.views.data'),
    (r'^xforms/data/(?P<formdef_id>\d+)/csv/?$', 'xformmanager.views.export_csv'),
    (r'^xforms/reports/$', 'xformmanager.views.reports'),
    (r'^xforms/reports/(?P<case_id>\d+)/?$', 'xformmanager.views.case_data'),
    (r'^xforms/reports/(?P<case_id>\d+)/csv/?$', 'xformmanager.views.case_export_csv'),
    (r'^xforms/reports/(?P<domain_id>\d+)/custom/(?P<report_name>.*)/?$', 'xformmanager.views.custom_report'),
    (r'^xforms/(?P<formdef_id>\d+)/submit$', 'xformmanager.views.submit_data'),
    (r'', include('xformmanager.api_.urls')),    
)
