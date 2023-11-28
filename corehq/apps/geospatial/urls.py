from django.conf.urls import re_path as url

from .dispatchers import CaseManagementMapDispatcher
from .views import (
    GeoPolygonView,
    GeospatialConfigPage,
    GPSCaptureView,
    MapboxOptimizationV2,
    CaseDisbursementAlgorithm,
    geospatial_default,
    get_paginated_cases_or_users,
    get_users_with_gps,
    mapbox_routing_status,
    routing_status_view,
)

urlpatterns = [
    url(r'^$', geospatial_default, name='geospatial_default'),
    url(r'^edit_geo_polygon/$', GeoPolygonView.as_view(),
        name=GeoPolygonView.urlname),
    url(r'^mapbox_routing/$',
        MapboxOptimizationV2.as_view(),
        name=MapboxOptimizationV2.urlname),
    url(r'^run_disbursement/$',
        CaseDisbursementAlgorithm.as_view(),
        name=CaseDisbursementAlgorithm.urlname),
    url(r'^mapbox_routing_status/(?P<poll_id>[\w-]+)/',
        mapbox_routing_status,
        name="mapbox_routing_status"),
    url(r'^routing_status/(?P<poll_id>[\w-]+)/',
        routing_status_view,
        name="routing_status"),
    url(r'^settings/$', GeospatialConfigPage.as_view(),
        name=GeospatialConfigPage.urlname),
    url(r'^gps_capture/json/$', get_paginated_cases_or_users,
        name='get_paginated_cases_or_users'),
    url(r'^gps_capture/$', GPSCaptureView.as_view(), name=GPSCaptureView.urlname),
    url(r'^users/json/$', get_users_with_gps, name='get_users_with_gps'),

    CaseManagementMapDispatcher.url_pattern(),
]
