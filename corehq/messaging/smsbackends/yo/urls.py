from django.conf.urls import patterns, url

urlpatterns = patterns('corehq.messaging.smsbackends.yo.views',
    url(r'^sms/?$', 'sms_in', name='sms_in'),
)
