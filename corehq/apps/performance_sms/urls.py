from django.conf.urls import patterns, url

urlpatterns = patterns('corehq.apps.performance_sms.views',
    url(r'^$', 'list_performance_configs', name='performance_sms.list_performance_configs'),
    url(r'^new/$', 'add_performance_config', name='performance_sms.add_performance_config'),
    url(r'^edit/(?P<config_id>[\w-]+)/$', 'edit_performance_config',
        name='performance_sms.edit_performance_config'),
    url(r'^delete/(?P<config_id>[\w-]+)/$', 'delete_performance_config',
        name='performance_sms.delete_performance_messages'),
    url(r'^sample/(?P<config_id>[\w-]+)/$', 'sample_performance_messages',
        name='performance_sms.sample_performance_messages'),
    url(r'^send/(?P<config_id>[\w-]+)/$', 'send_performance_messages',
        name='performance_sms.send_performance_messages'),
)
