from django.conf.urls import url

from corehq.apps.reminders.views import (
    KeywordsListView,
    AddStructuredKeywordView,
    EditStructuredKeywordView,
    AddNormalKeywordView,
    EditNormalKeywordView,
)

urlpatterns = [
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
]
