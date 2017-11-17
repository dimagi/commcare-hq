from __future__ import absolute_import
from django.conf.urls import url
from corehq.apps.case_search.views import CaseSearchView

urlpatterns = [
    url(r'^search/$', CaseSearchView.as_view(), name=CaseSearchView.urlname),
]
