from django.urls import re_path as url

from corehq.messaging.smsbackends.yo.views import YoIncomingSMSView

urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', YoIncomingSMSView.as_view(), name=YoIncomingSMSView.urlname),
]
