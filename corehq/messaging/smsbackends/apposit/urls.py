from django.urls import re_path as url
from corehq.messaging.smsbackends.apposit.views import AppositIncomingView


urlpatterns = [
    url(r'^in/(?P<api_key>[\w-]+)/$', AppositIncomingView.as_view(), name=AppositIncomingView.urlname),
]
