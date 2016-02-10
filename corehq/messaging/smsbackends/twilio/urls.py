from django.conf.urls import *
from corehq.messaging.smsbackends.twilio.views import (TwilioIncomingSMSView,
    TwilioIncomingIVRView)


urlpatterns = patterns('corehq.messaging.smsbackends.twilio.views',
    url(r'^sms/?$', 'sms_in', name='twilio_sms_in'),
    url(r'^ivr/?$', 'ivr_in', name='twilio_ivr_in'),
    url(r'^sms/(?P<api_key>[\w-]+)/?$', TwilioIncomingSMSView.as_view(),
        name=TwilioIncomingSMSView.urlname),
    url(r'^ivr/(?P<api_key>[\w-]+)/?$', TwilioIncomingIVRView.as_view(),
        name=TwilioIncomingIVRView.urlname),
)
