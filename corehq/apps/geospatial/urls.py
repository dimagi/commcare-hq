from django.urls import re_path as url

from .dispatchers import CaseManagementMapDispatcher
from .views import (
    CasesReassignmentView,
    GeoPolygonDetailView,
    GeoPolygonListView,
    GeospatialConfigPage,
    GPSCaptureView,
    CaseDisbursementAlgorithm,
    geospatial_default,
    get_paginated_cases_or_users,
    get_users_with_gps,
)

urlpatterns = [
    url(r'^$', geospatial_default, name='geospatial_default'),
    url(r'^edit_geo_polygon/$', GeoPolygonListView.as_view(), name=GeoPolygonListView.urlname),
    url(r'^edit_geo_polygon/(?P<pk>[\w-]+)/$', GeoPolygonDetailView.as_view(), name=GeoPolygonDetailView.urlname),
    url(r'^run_disbursement/$',
        CaseDisbursementAlgorithm.as_view(),
        name=CaseDisbursementAlgorithm.urlname),
    url(r'^settings/$', GeospatialConfigPage.as_view(),
        name=GeospatialConfigPage.urlname),
    url(r'^gps_capture/json/$', get_paginated_cases_or_users,
        name='get_paginated_cases_or_users'),
    url(r'^gps_capture/$', GPSCaptureView.as_view(), name=GPSCaptureView.urlname),
    url(r'^users/json/$', get_users_with_gps, name='get_users_with_gps'),
    url(r'^reassign_cases/$', CasesReassignmentView.as_view(), name=CasesReassignmentView.urlname),

    CaseManagementMapDispatcher.url_pattern(),
]
