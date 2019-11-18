from django.conf.urls import url

from corehq.messaging.smsbackends.tropo.views import TropoIncomingSMSView, TropoIncomingIVRView

urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', TropoIncomingSMSView.as_view(), name=TropoIncomingSMSView.urlname),
    url(r'^ivr/(?P<api_key>[\w-]+)/?$', TropoIncomingIVRView.as_view(), name=TropoIncomingIVRView.urlname),
]
