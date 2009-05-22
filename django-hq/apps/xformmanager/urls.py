from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^xforms/$', 'xformmanager.views.register_xform'),
    (r'^xforms/register/$', 'xformmanager.views.register_xform'),
    (r'^xforms/remove/(?P<form_id>\d+)$', 'xformmanager.views.remove_xform'),
    (r'^xforms/show/(?P<formdef_id>\d+)$', 'xformmanager.views.single_xform'),
    (r'^xforms/data/(?P<formdef_id>\d+)$', 'xformmanager.views.data'),
)
