from django.conf.urls import patterns, url

urlpatterns = patterns('corehq.apps.userreports.views',
    url(r'^reports/edit/(?P<report_id>[\w-]+)/$', 'edit_report', name='edit_configurable_report'),
    url(r'^data_sources/edit/(?P<config_id>[\w-]+)/$', 'edit_data_source', name='edit_configurable_data_source'),
    url(r'^data_sources/rebuild/(?P<config_id>[\w-]+)/$', 'rebuild_data_source', name='rebuild_configurable_data_source'),
    url(r'^data_sources/preview/(?P<config_id>[\w-]+)/$', 'preview_data_source', name='preview_configurable_data_source'),
)
