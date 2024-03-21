from django.urls import re_path as url
from corehq.messaging.smsbackends.push.views import PushIncomingView


urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', PushIncomingView.as_view(),
        name=PushIncomingView.urlname),
]
