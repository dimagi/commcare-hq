from __future__ import absolute_import
from django.conf.urls import url
from corehq.messaging.smsbackends.apposit.views import AppositIncomingView


urlpatterns = [
    url(r'^in/(?P<api_key>[\w-]+)/$', AppositIncomingView.as_view(), name=AppositIncomingView.urlname),
]
