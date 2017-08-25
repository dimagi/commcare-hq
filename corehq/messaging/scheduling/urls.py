from django.conf.urls import url

from corehq.messaging.scheduling.views import (
    BroadcastListView,
    CreateMessageView,
    EditMessageView,
    possible_sms_recipients,
)

urlpatterns = [
    url(r'^broadcasts/$', BroadcastListView.as_view(), name=BroadcastListView.urlname),
    url(r'^broadcasts/add/$', CreateMessageView.as_view(), name=CreateMessageView.urlname),
    url(r'^broadcasts/edit/(?P<broadcast_id>[\w-]+)/$', EditMessageView.as_view(), name=EditMessageView.urlname),
    url(r'^sms_recipients/$', possible_sms_recipients, name='possible_sms_recipients'),
]
