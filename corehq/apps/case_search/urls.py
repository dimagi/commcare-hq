from django.urls import re_path as url

from corehq.apps.case_search.views import CaseSearchView

urlpatterns = [
    url(r'^search/$', CaseSearchView.as_view(), name=CaseSearchView.urlname),
]
