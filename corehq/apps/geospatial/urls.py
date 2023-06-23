from django.conf.urls import re_path as url

from .dispatchers import CaseManagementMapDispatcher
from .views import (
    geospatial_default,
    GeoPolygonView,
    MapboxOptimizationV2,
    mapbox_routing_status,
)

urlpatterns = [
    url(r'^edit_geo_polygon/$', GeoPolygonView.as_view(),
        name=GeoPolygonView.urlname),
    url(r'^mapbox_routing/$',
        MapboxOptimizationV2.as_view(),
        name=MapboxOptimizationV2.urlname),
    url(r'^mapbox_routing_status/(?P<poll_id>[\w-]+)/',
        mapbox_routing_status,
        name="mapbox_routing_status"),
    url(r'^$', geospatial_default, name='geospatial_default'),
    CaseManagementMapDispatcher.url_pattern(),
]
