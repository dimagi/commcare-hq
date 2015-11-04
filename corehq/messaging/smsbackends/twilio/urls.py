from django.conf.urls import *

urlpatterns = patterns('corehq.messaging.smsbackends.twilio.views',
    url(r'^sms/?$', 'sms_in', name='twilio_sms_in'),
    url(r'^ivr/?$', 'ivr_in', name='twilio_ivr_in'),
)
