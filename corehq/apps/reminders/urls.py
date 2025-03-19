from django.urls import re_path as url

from corehq.apps.reminders.views import (
    AddNormalKeywordView,
    AddStructuredKeywordView,
    EditNormalKeywordView,
    EditStructuredKeywordView,
    ViewNormalKeywordView,
    ViewStructuredKeywordView,
    KeywordsListView,
)

urlpatterns = [
    url(r'^keywords/$', KeywordsListView.as_view(), name=KeywordsListView.urlname),
    url(r'^keywords/structured/add/$', AddStructuredKeywordView.as_view(),
        name=AddStructuredKeywordView.urlname),
    url(r'^keywords/normal/add/$', AddNormalKeywordView.as_view(),
        name=AddNormalKeywordView.urlname),
    url(r'^keywords/structured/view/(?P<keyword_id>[\w-]+)/$',
        ViewStructuredKeywordView.as_view(),
        name=ViewStructuredKeywordView.urlname),
    url(r'^keywords/structured/edit/(?P<keyword_id>[\w-]+)/$',
        EditStructuredKeywordView.as_view(),
        name=EditStructuredKeywordView.urlname),
    url(r'^keywords/normal/view/(?P<keyword_id>[\w-]+)/$',
        ViewNormalKeywordView.as_view(), name=ViewNormalKeywordView.urlname),
    url(r'^keywords/normal/edit/(?P<keyword_id>[\w-]+)/$',
        EditNormalKeywordView.as_view(), name=EditNormalKeywordView.urlname),
]
