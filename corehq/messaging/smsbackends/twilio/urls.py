from django.urls import re_path as url
from corehq.messaging.smsbackends.twilio.views import (TwilioIncomingSMSView,
    TwilioIncomingIVRView)


urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', TwilioIncomingSMSView.as_view(),
        name=TwilioIncomingSMSView.urlname),
    url(r'^ivr/(?P<api_key>[\w-]+)/?$', TwilioIncomingIVRView.as_view(),
        name=TwilioIncomingIVRView.urlname),
]
