from django.urls import re_path as url
from corehq.messaging.smsbackends.smsgh.views import SMSGHIncomingView

urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', SMSGHIncomingView.as_view(), name=SMSGHIncomingView.urlname),
]
