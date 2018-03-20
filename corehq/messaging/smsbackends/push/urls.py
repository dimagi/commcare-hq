from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from corehq.messaging.smsbackends.push.views import PushIncomingView


urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', PushIncomingView.as_view(),
        name=PushIncomingView.urlname),
]
