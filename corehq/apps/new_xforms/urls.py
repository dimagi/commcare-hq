from django.conf.urls.defaults import patterns

urlpatterns = patterns('corehq.apps.new_xforms.views',
    (r'view/(?P<app_id>\w+)/(?P<module_id>\w+)/(?P<form_id>\w+)/$',         'form_view'),
    (r'view/(?P<app_id>\w+)/(?P<module_id>\w+)/$',                          'module_view'),
    (r'view/(?P<app_id>\w+)/$',                                             'app_view'),
    (r'view/$',                                                             'forms'),
    #(r'$',                                                                  'forms'),

    (r'new_module/(?P<app_id>\w+)/$',                                       'new_module'),
    (r'new_app/$',                                                          'new_app'),
    (r'new_form/(?P<app_id>\w+)/(?P<module_id>\w+)/$',                      'new_form'),

    (r'delete_app/(?P<app_id>\w+)/$',                                       'delete_app'),
    (r'delete_module/(?P<app_id>\w+)/(?P<module_id>\w+)/$',                 'delete_module'),
    (r'delete_form/(?P<app_id>\w+)/(?P<module_id>\w+)/(?P<form_id>\w+)/$',  'delete_form'),

    (r'edit_form_attr/(?P<app_id>\w+)/(?P<module_id>\w+)/(?P<form_id>\w+)/(?P<attr>\w+)/$',
                                                                            'edit_form_attr'),

    (r'edit_module_detail/(?P<app_id>\w+)/(?P<module_id>\w+)/$',            'edit_module_detail'),
    #(r'edit_module_case_type/(?P<app_id>\w+)/(?P<module_id>\w+)/$',         'edit_module_case_type'),
    (r'edit_module_attr/(?P<app_id>\w+)/(?P<module_id>\w+)/(?P<attr>\w+)/$','edit_module_attr'),
    (r'delete_module_detail/(?P<app_id>\w+)/(?P<module_id>\w+)/$',          'delete_module_detail'),

    (r'edit_app_lang/(?P<app_id>\w+)/$',                                    'edit_app_lang'),
    (r'delete_app_lang/(?P<app_id>\w+)/$',                                  'delete_app_lang'),

    (r'swap/(?P<app_id>\w+)/(?P<key>\w+)/$',                                'swap'),

    (r'download/(?P<app_id>\w+)/suite.xml$',                                'download_suite'),
    (r'download/(?P<app_id>\w+)/profile.xml$',                              'download_profile'),
    (r'download/(?P<app_id>\w+)/(?P<lang>\w+)/app_strings.txt$',            'download_app_strings'),
    (r'download/(?P<app_id>\w+)/m(?P<module_id>\d+)/f(?P<form_id>\d+).xml$',
                                                                            'download_xform'),
    (r'download/(?P<app_id>\w+)/CommCare.jad',                              'download_jad'),
    #(r'download/(?P<app_id>\w+)/$',                                         'download'),

)