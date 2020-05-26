from django.conf.urls import url
from corehq.messaging.smsbackends.trumpia.views import TrumpiaIncomingView


urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', TrumpiaIncomingView.as_view(),
        name=TrumpiaIncomingView.urlname),
]
