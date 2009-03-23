from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^$', 'xformmanager.views.register_xform'),
    (r'^register_xform/$', 'xformmanager.views.register_xform'),
    (r'^single_xform/(?P<submit_id>\d+)$', 'xformmanager.views.single_xform'),
)
