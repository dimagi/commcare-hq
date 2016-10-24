from django.conf.urls import patterns, url

urlpatterns = patterns('corehq.messaging.smsbackends.megamobile.views',
    url(r'^sms/?$', 'sms_in', name='sms_in'),
)
