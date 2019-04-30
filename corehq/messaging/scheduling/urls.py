from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.messaging.scheduling.views import (
    BroadcastListView,
    ConditionalAlertListView,
    CreateConditionalAlertView,
    CreateScheduleView,
    DownloadConditionalAlertView,
    EditConditionalAlertView,
    EditScheduleView,
    MessagingDashboardView,
    UploadConditionalAlertView,
)

urlpatterns = [
    url(r'^dashboard/$', MessagingDashboardView.as_view(), name=MessagingDashboardView.urlname),
    url(r'^broadcasts/$', BroadcastListView.as_view(), name=BroadcastListView.urlname),
    url(r'^broadcasts/add/$', CreateScheduleView.as_view(), name=CreateScheduleView.urlname),
    url(r'^broadcasts/edit/(?P<broadcast_type>[\w-]+)/(?P<broadcast_id>[\w-]+)/$', EditScheduleView.as_view(),
        name=EditScheduleView.urlname),
    url(r'^conditional/$', ConditionalAlertListView.as_view(), name=ConditionalAlertListView.urlname),
    url(r'^conditional/add/$', CreateConditionalAlertView.as_view(), name=CreateConditionalAlertView.urlname),
    url(r'^conditional/edit/(?P<rule_id>[\w-]+)/$', EditConditionalAlertView.as_view(),
        name=EditConditionalAlertView.urlname),
    url(r'^conditional/download/$', DownloadConditionalAlertView.as_view(),
        name=DownloadConditionalAlertView.urlname),
    url(r'^conditional/upload/$', UploadConditionalAlertView.as_view(), name=UploadConditionalAlertView.urlname),
]
