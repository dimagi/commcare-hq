from django.urls import re_path as url

from corehq.apps.case_search.views import CaseSearchView, ProfileCaseSearchView

urlpatterns = [
    url(r'^search/$', CaseSearchView.as_view(), name=CaseSearchView.urlname),
    url(r'^profile/$', ProfileCaseSearchView.as_view(), name=ProfileCaseSearchView.urlname),
]
