from django.conf.urls import url

from corehq.messaging.smsbackends.unicel.views import UnicelIncomingSMSView

urlpatterns = [
    url(r'^in/(?P<api_key>[\w-]+)/?$', UnicelIncomingSMSView.as_view(), name=UnicelIncomingSMSView.urlname),
]
