from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    (r'(?P<domain>.+)/apps/view/(?P<app>.+)/(?P<module>.+)/(?P<form>.+)/$', 'hqui.views.forms'),
    (r'(?P<domain>.+)/apps/view/(?P<app>.+)/$', 'hqui.views.forms'),
    (r'(?P<domain>.+)/apps/edit_module/(?P<app>.+)/(?P<module>.+)/$', 'hqui.views.edit_module'),
    (r'(?P<domain>.+)/apps/new_app/$', 'hqui.views.new_app'),

)