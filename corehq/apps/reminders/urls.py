from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.apps.reminders.views import (
    CreateScheduledReminderView,
    EditScheduledReminderView,
    RemindersListView,
    CreateComplexScheduledReminderView,
    KeywordsListView,
    AddStructuredKeywordView,
    EditStructuredKeywordView,
    AddNormalKeywordView,
    EditNormalKeywordView,
    BroadcastListView,
    CreateBroadcastView,
    EditBroadcastView,
    CopyBroadcastView,
    ScheduledRemindersCalendarView,
    rule_progress,
)

urlpatterns = [
    url(r'^list/$', RemindersListView.as_view(), name=RemindersListView.urlname),
    url(r'^broadcasts/$', BroadcastListView.as_view(), name=BroadcastListView.urlname),
    url(r'^broadcasts/add/$', CreateBroadcastView.as_view(), name=CreateBroadcastView.urlname),
    url(r'^broadcasts/edit/(?P<broadcast_id>[\w-]+)/$', EditBroadcastView.as_view(),
        name=EditBroadcastView.urlname),
    url(r'^broadcasts/copy/(?P<broadcast_id>[\w-]+)/$', CopyBroadcastView.as_view(),
        name=CopyBroadcastView.urlname),
    url(r'^scheduled/', ScheduledRemindersCalendarView.as_view(), name=ScheduledRemindersCalendarView.urlname),
    url(r'^schedule/complex/$',
        CreateComplexScheduledReminderView.as_view(), name=CreateComplexScheduledReminderView.urlname),
    url(r'^schedule/(?P<handler_id>[\w-]+)/$',
        EditScheduledReminderView.as_view(), name=EditScheduledReminderView.urlname),
    url(r'^schedule/$',
        CreateScheduledReminderView.as_view(), name=CreateScheduledReminderView.urlname),
    url(r'^keywords/$', KeywordsListView.as_view(), name=KeywordsListView.urlname),
    url(r'^keywords/structured/add/$', AddStructuredKeywordView.as_view(),
        name=AddStructuredKeywordView.urlname),
    url(r'^keywords/normal/add/$', AddNormalKeywordView.as_view(),
        name=AddNormalKeywordView.urlname),
    url(r'^keywords/structured/edit/(?P<keyword_id>[\w-]+)/$',
        EditStructuredKeywordView.as_view(),
        name=EditStructuredKeywordView.urlname),
    url(r'^keywords/normal/edit/(?P<keyword_id>[\w-]+)/$',
        EditNormalKeywordView.as_view(), name=EditNormalKeywordView.urlname),
    url(r'^rule_progress/$', rule_progress, name='reminder_rule_progress'),
]
