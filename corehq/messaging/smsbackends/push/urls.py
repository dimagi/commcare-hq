from django.conf.urls import patterns, url
from corehq.messaging.smsbackends.push.views import PushIncomingView


urlpatterns = patterns('corehq.messaging.smsbackends.push.views',
    url(r'^sms/(?P<api_key>[\w-]+)/?$', PushIncomingView.as_view(),
        name=PushIncomingView.urlname),
)
