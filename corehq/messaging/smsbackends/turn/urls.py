from django.urls import re_path as url
from corehq.messaging.smsbackends.turn.views import TurnIncomingSMSView


urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', TurnIncomingSMSView.as_view(),
        name=TurnIncomingSMSView.urlname),
]
