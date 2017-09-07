from django.conf.urls import url

from corehq.messaging.scheduling.views import (
    BroadcastListView,
    CreateScheduleView,
    EditScheduleView,
    possible_sms_recipients,
)

urlpatterns = [
    url(r'^broadcasts/$', BroadcastListView.as_view(), name=BroadcastListView.urlname),
    url(r'^broadcasts/add/$', CreateScheduleView.as_view(), name=CreateScheduleView.urlname),
    url(r'^broadcasts/edit/(?P<broadcast_id>[\w-]+)/$', EditScheduleView.as_view(), name=EditScheduleView.urlname),
    url(r'^sms_recipients/$', possible_sms_recipients, name='possible_sms_recipients'),
]
