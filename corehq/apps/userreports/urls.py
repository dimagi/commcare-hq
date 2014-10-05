from django.conf.urls import patterns, url

urlpatterns = patterns('corehq.apps.userreports.views',
    url(r'^$', 'configurable_reports_home', name='configurable_reports_home'),
    url(r'^reports/create/$', 'create_report', name='create_configurable_report'),
    url(r'^reports/edit/(?P<report_id>[\w-]+)/$', 'edit_report', name='edit_configurable_report'),
    url(r'^reports/delete/(?P<report_id>[\w-]+)/$', 'delete_report', name='delete_configurable_report'),
    url(r'^data_sources/create/$', 'create_data_source', name='create_configurable_data_source'),
    url(r'^data_sources/edit/(?P<config_id>[\w-]+)/$', 'edit_data_source', name='edit_configurable_data_source'),
    url(r'^data_sources/delete/(?P<config_id>[\w-]+)/$', 'delete_data_source', name='delete_configurable_data_source'),
    url(r'^data_sources/rebuild/(?P<config_id>[\w-]+)/$', 'rebuild_data_source', name='rebuild_configurable_data_source'),
    url(r'^data_sources/preview/(?P<config_id>[\w-]+)/$', 'preview_data_source', name='preview_configurable_data_source'),
)
