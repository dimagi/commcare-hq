from django.conf.urls.defaults import patterns

urlpatterns = patterns('corehq.apps.new_xforms.views',
    (r'view/(?P<app_id>\w+)/(?P<module_id>\w+)/(?P<form_id>\w+)/$',         'forms'),
    (r'view/(?P<app_id>\w+)/(?P<module_id>\w+)/$',                          'forms'),
    (r'view/(?P<app_id>\w+)/$',                                             'forms'),
    (r'view/$',                                                             'forms'),

    (r'new_module/(?P<app_id>\w+)/$',                                       'new_module'),
    (r'new_app/$',                                                          'new_app'),
    (r'new_form/(?P<app_id>\w+)/(?P<module_id>\w+)/$',                      'new_form'),

    (r'delete_app/(?P<app_id>\w+)/$',                                       'delete_app'),
    (r'delete_module/(?P<app_id>\w+)/(?P<module_id>\w+)/$',                 'delete_module'),
    (r'delete_form/(?P<app_id>\w+)/(?P<module_id>\w+)/(?P<form_id>\w+)/$',  'delete_form'),
)