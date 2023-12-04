from django.db import models
from django.utils.translation import gettext as _

from corehq.apps.geospatial.const import GPS_POINT_CASE_PROPERTY
from corehq.apps.geospatial.routing_solvers import pulp


class GeoPolygon(models.Model):
    """
    A GeoJSON file representing a polygon shape
    """

    name = models.CharField(max_length=256)
    geo_json = models.JSONField(default=dict)
    domain = models.CharField(max_length=256, db_index=True)


class GeoConfig(models.Model):

    CUSTOM_USER_PROPERTY = 'custom_user_property'
    ASSIGNED_LOCATION = 'assigned_location'
    RADIAL_ALGORITHM = 'radial_algorithm'
    ROAD_NETWORK_ALGORITHM = 'road_network_algorithm'
    MIN_MAX_GROUPING = 'min_max_grouping'
    TARGET_SIZE_GROUPING = 'target_size_grouping'

    VALID_DISBURSEMENT_ALGORITHM_CLASSES = {
        RADIAL_ALGORITHM: pulp.RadialDistanceSolver,
        ROAD_NETWORK_ALGORITHM: pulp.RoadNetworkSolver,
    }

    VALID_LOCATION_SOURCES = [
        CUSTOM_USER_PROPERTY,
        ASSIGNED_LOCATION,
    ]
    VALID_DISBURSEMENT_ALGORITHMS = [
        (RADIAL_ALGORITHM, _('Radial Algorithm')),
        (ROAD_NETWORK_ALGORITHM, _('Road Network Algorithm')),
    ]
    VALID_GROUPING_METHODS = [
        (MIN_MAX_GROUPING, _('Min/Max Grouping')),
        (TARGET_SIZE_GROUPING, _('Target Size Grouping')),
    ]

    domain = models.CharField(max_length=256, db_index=True, primary_key=True)
    location_data_source = models.CharField(max_length=126, default=CUSTOM_USER_PROPERTY)
    user_location_property_name = models.CharField(max_length=256, default=GPS_POINT_CASE_PROPERTY)
    case_location_property_name = models.CharField(max_length=256, default=GPS_POINT_CASE_PROPERTY)

    selected_grouping_method = models.CharField(
        choices=VALID_GROUPING_METHODS,
        default=MIN_MAX_GROUPING,
        max_length=50
    )
    max_cases_per_group = models.IntegerField(null=True)
    min_cases_per_group = models.IntegerField(null=True)
    target_group_count = models.IntegerField(null=True)

    selected_disbursement_algorithm = models.CharField(
        choices=VALID_DISBURSEMENT_ALGORITHMS,
        default=ROAD_NETWORK_ALGORITHM,
        max_length=50
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._clear_caches()

    def delete(self, *args, **kwargs):
        self._clear_caches()
        return super().delete(*args, **kwargs)

    def _clear_caches(self):
        from .utils import get_geo_case_property, get_geo_user_property

        get_geo_case_property.clear(self.domain)
        get_geo_user_property.clear(self.domain)

    @property
    def disbursement_solver(self):
        return self.VALID_DISBURSEMENT_ALGORITHM_CLASSES[
            self.selected_disbursement_algorithm
        ]
