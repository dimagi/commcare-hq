from django.urls import path, re_path as url

from corehq.apps.case_search.endpoint_views import (
    CaseSearchEndpointDeactivateView,
    CaseSearchEndpointEditView,
    CaseSearchEndpointNewView,
    CaseSearchEndpointsView,
)
from corehq.apps.case_search.views import (
    CaseSearchView, CSQLFixtureExpressionView, ProfileCaseSearchView
)

urlpatterns = [
    url(r'^search/$', CaseSearchView.as_view(), name=CaseSearchView.urlname),
    url(r'^profile/$', ProfileCaseSearchView.as_view(), name=ProfileCaseSearchView.urlname),
    url(r'^csql_fixture_configuration/$', CSQLFixtureExpressionView.as_view(),
        name=CSQLFixtureExpressionView.urlname),
    path('endpoints/', CaseSearchEndpointsView.as_view(), name=CaseSearchEndpointsView.urlname),
    path('endpoints/new/', CaseSearchEndpointNewView.as_view(), name=CaseSearchEndpointNewView.urlname),
    path('endpoints/<int:endpoint_id>/edit/', CaseSearchEndpointEditView.as_view(),
         name=CaseSearchEndpointEditView.urlname),
    path('endpoints/<int:endpoint_id>/deactivate/', CaseSearchEndpointDeactivateView.as_view(),
         name=CaseSearchEndpointDeactivateView.urlname),
]
