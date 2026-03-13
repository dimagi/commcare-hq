from django.urls import re_path as url

from corehq.apps.case_search.views import (
    CaseSearchView, CSQLFixtureExpressionView, ProfileCaseSearchView
)
from corehq.apps.case_search.views.endpoints import (
    CaseSearchCapabilityView,
    CaseSearchEndpointDeactivateView,
    CaseSearchEndpointEditView,
    CaseSearchEndpointNewView,
    CaseSearchEndpointsView,
)

urlpatterns = [
    url(r'^search/$', CaseSearchView.as_view(), name=CaseSearchView.urlname),
    url(r'^profile/$', ProfileCaseSearchView.as_view(), name=ProfileCaseSearchView.urlname),
    url(r'^csql_fixture_configuration/$', CSQLFixtureExpressionView.as_view(),
    name=CSQLFixtureExpressionView.urlname),
    url(r'^endpoints/$',
        CaseSearchEndpointsView.as_view(),
        name=CaseSearchEndpointsView.urlname),
    url(r'^endpoints/new/$',
        CaseSearchEndpointNewView.as_view(),
        name=CaseSearchEndpointNewView.urlname),
    url(r'^endpoints/(?P<endpoint_id>\d+)/edit/$',
        CaseSearchEndpointEditView.as_view(),
        name=CaseSearchEndpointEditView.urlname),
    url(r'^endpoints/(?P<endpoint_id>\d+)/deactivate/$',
        CaseSearchEndpointDeactivateView.as_view(),
        name=CaseSearchEndpointDeactivateView.urlname),
    url(r'^endpoints/capability/$',
        CaseSearchCapabilityView.as_view(),
        name=CaseSearchCapabilityView.urlname),
]
