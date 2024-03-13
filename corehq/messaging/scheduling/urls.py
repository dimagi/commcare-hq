from corehq.apps.hqwebapp.decorators import waf_allow
from django.conf.urls import re_path as url

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
    messaging_image_download_view,
    messaging_image_upload_view,
)

urlpatterns = [
    url(r'^dashboard/$', MessagingDashboardView.as_view(), name=MessagingDashboardView.urlname),
    url(r'^broadcasts/$', BroadcastListView.as_view(), name=BroadcastListView.urlname),
    url(r'^broadcasts/add/$', waf_allow('XSS_BODY')(CreateScheduleView.as_view()),
        name=CreateScheduleView.urlname),
    url(r'^broadcasts/edit/(?P<broadcast_type>[\w-]+)/(?P<broadcast_id>[\w-]+)/$', EditScheduleView.as_view(),
        name=EditScheduleView.urlname),
    url(r'^conditional/$', ConditionalAlertListView.as_view(), name=ConditionalAlertListView.urlname),
    # System URL only, to enabling data refresh without logging as user activity
    url(r'^conditional/refresh/$', ConditionalAlertListView.as_view(),
        name=ConditionalAlertListView.refresh_urlname),
    url(r'^conditional/add/$', waf_allow('XSS_BODY')(CreateConditionalAlertView.as_view()),
        name=CreateConditionalAlertView.urlname),
    url(r'^conditional/edit/(?P<rule_id>[\w-]+)/$', waf_allow('XSS_BODY')(EditConditionalAlertView.as_view()),
        name=EditConditionalAlertView.urlname),
    url(r'^conditional/download/$', DownloadConditionalAlertView.as_view(),
        name=DownloadConditionalAlertView.urlname),
    url(r'^conditional/upload/$', UploadConditionalAlertView.as_view(), name=UploadConditionalAlertView.urlname),
    url(r'^image/upload/$', messaging_image_upload_view, name="upload_messaging_image"),
    url(r'^image/download/(?P<image_key>[\w-]+)$', messaging_image_download_view, name="download_messaging_image"),
]
