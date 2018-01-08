from __future__ import absolute_import
from django.conf.urls import url
from corehq.messaging.smsbackends.twilio.views import TwilioIncomingSMSView


urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', TwilioIncomingSMSView.as_view(),
        name=TwilioIncomingSMSView.urlname),
]
