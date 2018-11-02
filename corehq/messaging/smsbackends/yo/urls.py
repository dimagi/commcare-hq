from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.messaging.smsbackends.yo.views import YoIncomingSMSView

urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', YoIncomingSMSView.as_view(), name=YoIncomingSMSView.urlname),
]
