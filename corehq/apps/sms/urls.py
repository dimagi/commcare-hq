from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('corehq.apps.sms.views',
    url(r'^$', 'default', name='sms_default'),
    url(r'^post/?$', 'post', name='sms_post'),
    url(r'^send_to_recipients/$', 'send_to_recipients'),
    url(r'^compose/$', 'compose_message', name='sms_compose_message'),
    url(r'^message_test/(?P<phone_number>\d+)/$', 'message_test', name='message_test'),
    url(r'^api/send_sms/$', 'api_send_sms', name='api_send_sms'),
    url(r'^history/$', 'messaging', name='messaging'),
)
