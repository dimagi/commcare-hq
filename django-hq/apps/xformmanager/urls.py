from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^$', 'xformmanager.views.register_xform'),
    (r'^register_xform/$', 'xformmanager.views.register_xform'),
    (r'^single_xform/(?P<submit_id>\d+)$', 'xformmanager.views.single_xform'),
    #(r'^formmanager/', 'admin.site.root'),
    #(r'^post/$', 'xformmanager.views.post_xml'),
    ##(r'^list/$', 'xformmanager.views.list_posted'),
    ##(r'^show_xml/$', 'xformmanager.views.show_xml'),
    #(r'^list_xforms/$', 'xformmanager.views.list_xforms'),
)
