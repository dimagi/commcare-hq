from django.conf.urls import patterns, url

urlpatterns = patterns('corehq.apps.performance_sms.views',
    url(r'^$', 'list_performance_configs', name='performance_sms.list_performance_configs'),

)
