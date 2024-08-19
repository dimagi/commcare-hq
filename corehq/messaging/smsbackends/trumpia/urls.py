from django.urls import re_path as url

from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.messaging.smsbackends.trumpia.views import TrumpiaIncomingView


urlpatterns = [
    url(r'^sms/(?P<api_key>[\w-]+)/?$', waf_allow('XSS_QUERYSTRING')(TrumpiaIncomingView.as_view()),
        name=TrumpiaIncomingView.urlname),
]
