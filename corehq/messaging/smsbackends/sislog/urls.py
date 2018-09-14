from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.messaging.smsbackends.sislog.views import SislogIncomingSMSView

urlpatterns = [
    url(r'^in/(?P<api_key>[\w-]+)/?$', SislogIncomingSMSView.as_view(), name=SislogIncomingSMSView.urlname),
]
