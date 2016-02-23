from django.conf.urls import *
from corehq.messaging.smsbackends.smsgh.views import SMSGHIncomingView

urlpatterns = patterns('corehq.messaging.smsbackends.smsgh.views',
    url(r'^sms/(?P<api_key>[\w-]+)/?$', SMSGHIncomingView.as_view(), name=SMSGHIncomingView.urlname),
)
