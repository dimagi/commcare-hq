from django.db import models
from dataclasses import dataclass

import geopandas as gpd
from geopy.distance import great_circle
from shapely.geometry import Point

from .exceptions import InvalidCoordinate, InvalidDistributionParam
from corehq.apps.geospatial.const import GPS_POINT_CASE_PROPERTY


@dataclass
class GeoObject:
    """
    `lat` and `lon` are assumed to be in a EPSG:4326 map projection.
    """
    id: str
    lon: float
    lat: float

    def __post_init__(self):
        if self.lon < -180 or self.lon > 180:
            raise InvalidCoordinate("Invalid lon value. Must be [-180, 180]")
        if self.lat < -90 or self.lat > 90:
            raise InvalidCoordinate("Invalid lat value. Must be [-90, 90]")

    def get_point(self):
        return Point(self.lon, self.lat)

    def get_info(self):
        return {
            'id': self.id,
            'geometry': self.get_point()
        }


@dataclass
class Objective(GeoObject):
    is_assigned: bool = False

    def get_info(self):
        info = super().get_info()
        info['is_assigned'] = self.is_assigned
        return info


class ObjectiveAllocator:
    """
    :param users: Should be a list of objects of class/subclass `GeoObject` with id of `user_id`
    :param objectives: Should be a list of objects of class/subclass `GeoObject` with id of `case_id`
    :param max_distance: The maximum distance allowed for an objective to be assignable to a user (unit is km)
        If set to None, the maximum distance will not be limited
    :param max_assignable: The maximum number of objectives that can be assigned to a user
        If set to None, the maximum assignable count will not be limited
    """
    def __init__(self, users, objectives, max_distance=None, max_assignable=None):
        if (max_distance and max_distance < 0) or (max_assignable and max_assignable < 0):
            raise InvalidDistributionParam(
                "Maximum distance and assignable count must be positive numbers"
            )

        self.users = users
        self.objectives = objectives
        self.max_distance = max_distance
        self.max_assignable = max_assignable

    def _create_dataframe(self, item_list):
        return gpd.GeoDataFrame([item.get_info() for item in item_list]).set_index('id')

    def get_unassigned_objectives(self, id_only=True):
        return [
            (objective.id if id_only else objective) for objective in self.objectives
            if not objective.is_assigned
        ]

    def allocate_objectives(self):
        """
        Allocates objectives to given users within the constraints of `max_distance` and `max_assignable`.
        Returns a dict with user_id as the key and a list of assigned objective_id as the value.
            {
                'user_a': ['obj_a', 'obj_b']
            }
        Users that have not been assigned at least one objective will not be included in the final output.
        """
        if not (self.users and self.objectives):
            return {}

        gdf = self._create_dataframe(self.users)

        user_assignment = {}
        for obj in self.objectives:
            # We have run out of available users, and so we cannot assign any more objectives
            if not len(gdf):
                break

            obj_point = obj.get_point()
            users_dist_to_obj = gdf.distance(obj_point)

            closest_user_id = users_dist_to_obj.idxmin()
            if self.max_distance:
                closest_user_geo = gdf.loc[closest_user_id].geometry
                closest_user_dist = great_circle(
                    (closest_user_geo.y, closest_user_geo.x),  # Format (lat, lon)
                    (obj_point.y, obj_point.x)
                ).kilometers

                # If objective is too far for closest user,
                # then no user can access this objective and we'll skip it
                if closest_user_dist > self.max_distance:
                    continue

            if closest_user_id not in user_assignment:
                user_assignment[closest_user_id] = []
            user_assignment[closest_user_id].append(obj.id)
            obj.is_assigned = True

            # Remove user from selection if they've hit their assignable limit
            if self.max_assignable and len(user_assignment[closest_user_id]) >= self.max_assignable:
                gdf.drop(closest_user_id, inplace=True)

        return user_assignment


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

    VALID_LOCATION_SOURCES = [
        CUSTOM_USER_PROPERTY,
        ASSIGNED_LOCATION,
    ]

    domain = models.CharField(max_length=256, db_index=True, primary_key=True)
    location_data_source = models.CharField(max_length=126, default=CUSTOM_USER_PROPERTY)
    user_location_property_name = models.CharField(max_length=256, default=GPS_POINT_CASE_PROPERTY)
    case_location_property_name = models.CharField(max_length=256, default=GPS_POINT_CASE_PROPERTY)
