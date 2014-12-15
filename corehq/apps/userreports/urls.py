from django.conf.urls import patterns, url

urlpatterns = patterns('corehq.apps.userreports.views',
    url(r'^$', 'configurable_reports_home', name='configurable_reports_home'),
    url(r'^reports/create/$', 'create_report', name='create_configurable_report'),
    url(r'^reports/import/$', 'import_report', name='import_configurable_report'),
    url(r'^reports/edit/(?P<report_id>[\w-]+)/$', 'edit_report', name='edit_configurable_report'),
    url(r'^reports/source/(?P<report_id>[\w-]+)/$', 'report_source_json', name='configurable_report_json'),
    url(r'^reports/delete/(?P<report_id>[\w-]+)/$', 'delete_report', name='delete_configurable_report'),
    url(r'^data_sources/create/$', 'create_data_source', name='create_configurable_data_source'),
    url(r'^data_sources/create_from_app/$', 'create_data_source_from_app',
        name='create_configurable_data_source_from_app'),
    url(r'^data_sources/create_form_from_app/$', 'create_form_data_source_from_app',
        name='create_configurable_form_data_source_from_app'),
    url(r'^data_sources/edit/(?P<config_id>[\w-]+)/$', 'edit_data_source', name='edit_configurable_data_source'),
    url(r'^data_sources/delete/(?P<config_id>[\w-]+)/$', 'delete_data_source',
        name='delete_configurable_data_source'),
    url(r'^data_sources/rebuild/(?P<config_id>[\w-]+)/$', 'rebuild_data_source',
        name='rebuild_configurable_data_source'),
    url(r'^data_sources/preview/(?P<config_id>[\w-]+)/$', 'preview_data_source',
        name='preview_configurable_data_source'),

    # apis
    url(r'^api/choice_list/(?P<report_id>[\w-]+)/(?P<filter_id>[\w-]+)/$', 'choice_list_api', name='choice_list_api'),
)
