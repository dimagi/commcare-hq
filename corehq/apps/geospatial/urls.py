from django.conf.urls import re_path as url

from .dispatchers import CaseManagementMapDispatcher
from .views import (
    geospatial_default,
    MapboxOptimizationV2,
    mapbox_routing_status
)

urlpatterns = [
    url(r'^$', geospatial_default, name='geospatial_default'),
    CaseManagementMapDispatcher.url_pattern(),
    url(r'^mapbox_routing/$',
        MapboxOptimizationV2.as_view(),
        name=MapboxOptimizationV2.urlname),
    url(r'^mapbox_routing_status/(?P<poll_id>[\w-]+)/',
        mapbox_routing_status,
        name="mapbox_routing_status"),
]
