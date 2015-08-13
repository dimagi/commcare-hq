from django.conf.urls import patterns, url

urlpatterns = patterns('corehq.apps.performance_sms.views',
    url(r'^$', 'list_performance_configs', name='performance_sms.list_performance_configs'),
    url(r'^new/$', 'add_performance_config', name='performance_sms.add_performance_config'),
    url(r'^edit/(?P<config_id>[\w-]+)/$', 'edit_performance_config', name='performance_sms.edit_performance_config'),
)
