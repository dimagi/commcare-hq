from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^$', 'xformmanager.views.register_xform'),
    (r'^register_xform/$', 'xformmanager.views.register_xform'),
    (r'^single_xform/(?P<formdef_name>[^/]+)$', 'xformmanager.views.single_xform'),
    (r'^data/(?P<formdef_name>[^/]+)$', 'xformmanager.views.data'),
)
