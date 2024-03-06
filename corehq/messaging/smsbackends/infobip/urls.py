from django.urls import re_path as url
from corehq.messaging.smsbackends.infobip.views import InfobipIncomingMessageView


urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$$', InfobipIncomingMessageView.as_view(),
        name=InfobipIncomingMessageView.urlname)
]
