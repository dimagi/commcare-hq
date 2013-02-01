from django.conf.urls.defaults import patterns, url, include
from corehq.apps.hqmedia.urls import application_urls as hqmedia_urls

app_urls = patterns('corehq.apps.app_manager.views',
    url(r'^$', 'view_app', name='view_app'),
    url(r'^releases/$', 'release_manager', name='release_manager'),
    url(r'^releases/json/$', 'paginate_releases', name='paginate_releases'),
    url(r'^releases/release/(?P<saved_app_id>[\w-]+)/$', 'release_build', name='release_build'),
    url(r'^releases/unrelease/(?P<saved_app_id>[\w-]+)/$', 'release_build', name='unrelease_build', kwargs={'is_released': False}),
    url(r'^modules-(?P<module_id>[\w-]+)/$', 'view_module', name='view_module'),
    url(r'^modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/$', 'view_form', name='view_form'),
    url(r'^user_registration/$', 'view_user_registration', name='view_user_registration'),
    url(r'^user_registration/source/$', 'user_registration_source', name='user_registration_source'),
    url(r'^modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/source/$', 'form_source', name='form_source'),
    url(r'^summary/$', 'app_summary', name='app_summary'),
    url(r'^exchange_summary/$', 'app_summary_from_exchange', name='exchange_app_summary'),
)

urlpatterns = patterns('corehq.apps.app_manager.views',
    url(r'^$', 'default'),
    (r'^xform/(?P<form_unique_id>[\w-]+)/$',                                    'xform_display'),
 url(r'^browse/(?P<app_id>[\w-]+)/modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/source/$',
                                                                            'get_xform_source',
                                                                       name='get_xform_source'),
 url(r'^browse/(?P<app_id>[\w-]+)/user_registration/source/$',                'get_user_registration_source',
                                                                       name='get_user_registration_source'),
    (r'^casexml/(?P<form_unique_id>[\w-]+)/$',                                  'form_casexml'),
    (r'^source/(?P<app_id>[\w-]+)/$',                                           'app_source'),
 url(r'^import_app/$',                                                       'import_app', name='import_app'),
    (r'^import_factory_app/$',                                               'import_factory_app'),
    (r'^import_factory_module/(?P<app_id>[\w-]+)/$',                            'import_factory_module'),
    (r'^import_factory_form/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/$',           'import_factory_form'),
    url(r'^view/(?P<app_id>[\w-]+)/', include(app_urls)),

    (r'^new_module/(?P<app_id>[\w-]+)/$',                                       'new_module'),
 url(r'^new_app/$',                                                          'new_app', name='new_app'),
    (r'^new_form/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/$',                      'new_form'),

    (r'^delete_app/(?P<app_id>[\w-]+)/$',                                       'delete_app'),
 url(r'^delete_module/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/$',                 'delete_module', name="delete_module"),
 url(r'^delete_form/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/(?P<form_id>[\w-]+)/$', 'delete_form', name="delete_form"),

 url(r'^undo_delete_app/(?P<record_id>[\w-]+)/$',    'undo_delete_app',      name='undo_delete_app'),
 url(r'^undo_delete_module/(?P<record_id>[\w-]+)/$', 'undo_delete_module',   name='undo_delete_module'),
 url(r'^undo_delete_form/(?P<record_id>[\w-]+)/$',   'undo_delete_form',     name='undo_delete_form'),

 url(r'^edit_form_attr/(?P<app_id>[\w-]+)/(?P<unique_form_id>[\w-]+)/(?P<attr>[\w-]+)/$',
                                                                            'edit_form_attr',
                                                                       name='edit_form_attr'),
    url(r'^patch_xform/(?P<app_id>[\w-]+)/(?P<unique_form_id>[\w-]+)/$', 'patch_xform', name='patch_xform'),
    url(r'^validate_form_for_build/(?P<app_id>[\w-]+)/(?P<unique_form_id>[\w-]+)/$', 'validate_form_for_build', name='validate_form_for_build'),
    (r'^rename_language/(?P<form_unique_id>[\w-]+)/$',                          'rename_language'),
    (r'^validate_langcode/(?P<app_id>[\w-]+)/$', 'validate_language'),
    (r'^edit_form_actions/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/(?P<form_id>[\w-]+)/$',
                                                                            'edit_form_actions'),
    # multimedia stuff
    url(r'^multimedia/(?P<app_id>[\w-]+)/download/$',
        'multimedia_list_download', name='multimedia_list_download'),
    (r'^(?P<app_id>[\w-]+)/multimedia/', include(hqmedia_urls)),

 url(r'^edit_module_detail_screens/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/$',    'edit_module_detail_screens',
                                                                       name='edit_module_detail_screens'),
    (r'^edit_module_attr/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/(?P<attr>[\w-]+)/$','edit_module_attr'),
    (r'^delete_module_detail/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/$',          'delete_module_detail'),

    (r'^commcare_profile/(?P<app_id>[\w-]+)/$',                                'commcare_profile'),
 url(r'^edit_commcare_profile/(?P<app_id>[\w-]+)/$',                           'edit_commcare_profile',
                                                                       name='edit_commcare_profile'),
    url(r'^edit_app_langs/(?P<app_id>[\w-]+)/$', 'edit_app_langs', name='edit_app_langs'),
 url(r'^edit_app_attr/(?P<app_id>[\w-]+)/(?P<attr>[\w-]+)/$',                      'edit_app_attr',
                                                                       name='edit_app_attr'),
 url(r'^edit_app_translations/(?P<app_id>[\w-]+)/$',               'edit_app_translations', name='edit_app_translations'),

    (r'^rearrange/(?P<app_id>[\w-]+)/(?P<key>[\w-]+)/$',                           'rearrange'),

    (r'^odk/(?P<app_id>[\w-]+)/qr_code/$',                                       'odk_qr_code'),
    (r'^odk/(?P<app_id>[\w-]+)/install/$',                                       'odk_install'),

    (r'^save/(?P<app_id>[\w-]+)/$',                                             'save_copy'),
    (r'^revert/(?P<app_id>[\w-]+)/$',                                           'revert_to_copy'),
    (r'^delete_copy/(?P<app_id>[\w-]+)/$',                                      'delete_copy'),

    url(r'^emulator/(?P<app_id>[\w-]+)/$', 'emulator_handler', name="emulator"),
    (r'^emulator/(?P<app_id>[\w-]+)/CommCare\.jar$',                            'emulator_commcare_jar'),
    url(r'^download/(?P<app_id>[\w-]+)/$', 'download_index', {}, 'download_index'),
    url(r'^download/(?P<app_id>[\w-]+)/(?P<path>.*)$', 'download_file', name='app_download_file'),
    url(r'^download/(?P<app_id>[\w-]+)/', include('corehq.apps.app_manager.download_urls')),
    url(r'^formdefs/(?P<app_id>[\w-]+)/', 'formdefs', name='formdefs'),
)
