from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.messaging.smsbackends.tropo.views import ivr_in, sms_in, TropoIncomingSMSView, TropoIncomingIVRView

urlpatterns = [
    url(r'^sms/?$', sms_in, name='sms_in'),
    url(r'^ivr/?$', ivr_in, name='ivr_in'),
    url(r'^sms/(?P<api_key>[\w-]+)/?$', TropoIncomingSMSView.as_view(), name=TropoIncomingSMSView.urlname),
    url(r'^ivr/(?P<api_key>[\w-]+)/?$', TropoIncomingIVRView.as_view(), name=TropoIncomingIVRView.urlname),
]
