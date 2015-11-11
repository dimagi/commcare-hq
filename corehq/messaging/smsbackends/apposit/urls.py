from django.conf.urls import *
from corehq.messaging.smsbackends.apposit.views import AppositIncomingView


urlpatterns = patterns('corehq.messaging.smsbackends.apposit.views',
    url(r'^in/(?P<api_key>[\w-]+)/$', AppositIncomingView.as_view(), name=AppositIncomingView.urlname),
)
