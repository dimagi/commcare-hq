from __future__ import absolute_import
from django.conf.urls import url
from corehq.messaging.smsbackends.smsgh.views import SMSGHIncomingView

urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', SMSGHIncomingView.as_view(), name=SMSGHIncomingView.urlname),
]
