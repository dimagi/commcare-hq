from django.db import models
from django.utils.translation import gettext as _
from django.forms.models import model_to_dict
from django.core.exceptions import ValidationError

from corehq.apps.geospatial.const import (
    GPS_POINT_CASE_PROPERTY,
    TRAVEL_MODE_WALKING,
    TRAVEL_MODE_CYCLING,
    TRAVEL_MODE_DRIVING,
)
from corehq.apps.geospatial.routing_solvers import pulp
from corehq.motech.const import ALGO_AES_CBC
from corehq.motech.utils import (
    b64_aes_cbc_decrypt,
    b64_aes_cbc_encrypt,
)


class GeoPolygon(models.Model):
    """
    A GeoJSON file representing a polygon shape
    """

    name = models.CharField(max_length=256)
    geo_json = models.JSONField(default=dict)
    domain = models.CharField(max_length=256, db_index=True)


def validate_travel_mode(value):
    valid_modes = [
        TRAVEL_MODE_WALKING,
        TRAVEL_MODE_CYCLING,
        TRAVEL_MODE_DRIVING
    ]
    if value not in valid_modes:
        raise ValidationError(
            _("%(value)s is not a valid travel mode"),
            params={"value": value},
        )


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
    VALID_TRAVEL_MODES = [
        (TRAVEL_MODE_WALKING, _("Walking")),
        (TRAVEL_MODE_CYCLING, _("Cycling")),
        (TRAVEL_MODE_DRIVING, _("Driving")),
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
    travel_mode = models.CharField(
        choices=VALID_TRAVEL_MODES,
        default=TRAVEL_MODE_DRIVING,
        max_length=50,
    )
    selected_disbursement_algorithm = models.CharField(
        choices=VALID_DISBURSEMENT_ALGORITHMS,
        default=RADIAL_ALGORITHM,
        max_length=50
    )
    api_token = models.CharField(max_length=255, blank=True, null=True, db_column="api_token")
    flag_assigned_cases = models.BooleanField(default=False)

    @property
    def supports_travel_mode(self):
        return self.selected_disbursement_algorithm == self.ROAD_NETWORK_ALGORITHM

    @property
    def disbursement_solver(self):
        return self.VALID_DISBURSEMENT_ALGORITHM_CLASSES[
            self.selected_disbursement_algorithm
        ]

    @property
    def plaintext_api_token(self):
        if self.api_token:
            ciphertext = self.api_token.split('$', 2)[2]
            return b64_aes_cbc_decrypt(ciphertext)
        return self.api_token

    @plaintext_api_token.setter
    def plaintext_api_token(self, value):
        if value is None:
            self.api_token = None
        else:
            assert isinstance(value, str), "Only string values allowed for api token"

            if value and not value.startswith(f'${ALGO_AES_CBC}$'):
                ciphertext = b64_aes_cbc_encrypt(value)
                self.api_token = f'${ALGO_AES_CBC}${ciphertext}'
            else:
                raise Exception("Unexpected value set for plaintext api token")

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
        config = model_to_dict(self, fields=fields)

        if fields is None or 'plaintext_api_token' in fields:
            config['plaintext_api_token'] = self.plaintext_api_token
        return config
