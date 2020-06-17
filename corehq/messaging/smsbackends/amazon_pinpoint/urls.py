from django.conf.urls import url
from corehq.messaging.smsbackends.amazon_pinpoint.views import PinpointIncomingMessageView


urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$$', PinpointIncomingMessageView.as_view(),
        name=PinpointIncomingMessageView.urlname)
]
