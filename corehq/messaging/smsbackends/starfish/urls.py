from django.urls import re_path as url
from corehq.messaging.smsbackends.starfish.views import StarfishIncomingView


urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', StarfishIncomingView.as_view(),
        name=StarfishIncomingView.urlname),
]
