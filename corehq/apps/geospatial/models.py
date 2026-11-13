from django.db import models
from django.utils.translation import gettext as _
from django.forms.models import model_to_dict

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
    MIN_MAX_GROUPING = 'min_max_grouping'
    TARGET_SIZE_GROUPING = 'target_size_grouping'

    VALID_DISBURSEMENT_ALGORITHM_CLASSES = {
        RADIAL_ALGORITHM: pulp.RadialDistanceSolver,
    }

    VALID_LOCATION_SOURCES = [
        CUSTOM_USER_PROPERTY,
        ASSIGNED_LOCATION,
    ]
    VALID_DISBURSEMENT_ALGORITHMS = [
        (RADIAL_ALGORITHM, _('Radial Algorithm')),
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

    max_cases_per_user = models.IntegerField(null=True)
    min_cases_per_user = models.IntegerField(default=1)
    max_case_distance = models.IntegerField(null=True)  # km
    max_case_travel_time = models.IntegerField(null=True)  # minutes
    selected_disbursement_algorithm = models.CharField(
        choices=VALID_DISBURSEMENT_ALGORITHMS,
        default=RADIAL_ALGORITHM,
        max_length=50
    )
    flag_assigned_cases = models.BooleanField(default=False)

    @property
    def disbursement_solver(self):
        return self.VALID_DISBURSEMENT_ALGORITHM_CLASSES[
            self.selected_disbursement_algorithm
        ]

    def as_dict(self, fields=None):
        """
        Returns the model as a dictionary.

        :param fields: Specify the specific fields you're interested in. A value of None will return all fields.

        Example usage:
        >>> config.as_dict(fields=[])
        {}
        >>> config.as_dict(fields=['domain'])
        {'domain': <value>}
        """
        return model_to_dict(self, fields=fields)
