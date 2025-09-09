from django.urls import re_path as url

from corehq.apps.case_search.views import (
    CaseSearchView, CSQLFixtureExpressionView, ProfileCaseSearchView
)

urlpatterns = [
    url(r'^search/$', CaseSearchView.as_view(), name=CaseSearchView.urlname),
    url(r'^profile/$', ProfileCaseSearchView.as_view(), name=ProfileCaseSearchView.urlname),
    url(r'^csql_fixture_configuration/$', CSQLFixtureExpressionView.as_view(),
    name=CSQLFixtureExpressionView.urlname),
]
