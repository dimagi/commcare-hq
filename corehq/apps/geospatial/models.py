from dataclasses import dataclass

import geopandas as gpd
from geopy.distance import great_circle
from shapely.geometry import Point

from .exceptions import InvalidCoordinate, InvalidDistributionParam


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

    def group_objectives(self):
        """
        Group objectives that are closest together, within the constraints of `max_distance` and `max_assignable`.
        Returns a 2D list containing all the objectives groups.
        [['obj_a', 'obj_b']]

        At least one of the constraints has to be non-null, otherwise will simply return the list of objective ids.
        """
        if not self.objectives:
            return []
        if not self.max_distance and not self.max_assignable:
            return [[obj.id for obj in self.objectives]]

        self.objectives.sort(key=lambda x: (x.lat, x.lon))

        bins = []
        current_bin = [self.objectives[0].id]
        bins.append(current_bin)

        for i in range(1, len(self.objectives)):
            current_objective = self.objectives[i]
            previous_object = self.objectives[i - 1]

            distance = great_circle(
                (current_objective.lat, current_objective.lon),
                (previous_object.lat, previous_object.lon)
            ).kilometers

            # One of the constraints might be null, so we need to do the appropriate constraints check based
            # on which constraints are non-null
            if self.max_distance and self.max_assignable:
                constraints_met = distance <= self.max_distance and len(current_bin) <= self.max_assignable
            elif self.max_distance:
                constraints_met = distance <= self.max_distance
            else:
                constraints_met = len(current_bin) <= self.max_assignable

            if constraints_met:
                current_bin.append(current_objective.id)
            else:
                current_bin = [current_objective.id]
                bins.append(current_bin)

        return bins
