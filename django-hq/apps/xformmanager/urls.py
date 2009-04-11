from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^$', 'xformmanager.views.register_xform'),
    (r'^register_xform/$', 'xformmanager.views.register_xform'),
    (r'^remove_xform/(?P<form_id>\d+)$', 'xformmanager.views.remove_xform'),
    (r'^single_xform/(?P<formdef_id>\d+)$', 'xformmanager.views.single_xform'),
    (r'^data/(?P<formdef_id>\d+)$', 'xformmanager.views.data'),
)
