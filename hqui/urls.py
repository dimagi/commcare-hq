from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    (r'(?P<domain>.+)/forms/view/(?P<app>.+)/(?P<module>.+)/(?P<form>.+)/$', 'hqui.views.forms'),
    (r'(?P<domain>.+)/forms/view/(?P<app>.+)/(?P<module>.+)/$', 'hqui.views.forms'),
    (r'(?P<domain>.+)/forms/view/(?P<app>.+)/$', 'hqui.views.forms'),
    (r'(?P<domain>.+)/forms/new_module/(?P<app>.+)/$', 'hqui.views.new_module'),
    (r'(?P<domain>.+)/forms/new_app/$', 'hqui.views.new_app'),
    (r'(?P<domain>.+)/forms/new_form/(?P<app>.+)/(?P<module>.+)/$', 'hqui.views.new_form'),
    (r'(?P<domain>.+)/forms/delete_form/(?P<app>.+)/(?P<module>.+)/(?P<form>.+)/$', 'hqui.views.delete_form'),
)