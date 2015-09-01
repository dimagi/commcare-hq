from django.conf.urls import *

urlpatterns = patterns('commcarehq.messaging.smsbackends.tropo.views',
    url(r'^sms/?$', 'sms_in', name='sms_in'),
    url(r'^ivr/?$', 'ivr_in', name='ivr_in'),
)
