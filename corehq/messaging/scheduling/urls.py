from django.conf.urls import url

from corehq.messaging.scheduling.views import (
    BroadcastListView,
    possible_sms_recipients,
)

urlpatterns = [
    url(r'^broadcasts/$', BroadcastListView.as_view(), name=BroadcastListView.urlname),
    url(r'^sms_recipients/$', possible_sms_recipients, name='possible_sms_recipients'),
]
