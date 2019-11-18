from django.conf.urls import url

from corehq.messaging.smsbackends.sislog.views import SislogIncomingSMSView

urlpatterns = [
    url(r'^in/(?P<api_key>[\w-]+)/?$', SislogIncomingSMSView.as_view(), name=SislogIncomingSMSView.urlname),
]
