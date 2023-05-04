from math import radians, cos, sin, asin, sqrt
from shapely.geometry import Point
import geopandas as gpd


class GeoObject:
    """
    `lat` and `lon` are assumed to be in a EPSG:4326 map projection.
    """
    def __init__(self, id, lon, lat):
        if lon < -180 or lon > 180:
            raise ValueError("Invalid lon value. Must be [-180, 180]")
        if lat < -90 or lat > 90:
            raise ValueError("Invalid lat value. Must be [-90, 90]")

        self.id = id
        self.lat = lat
        self.lon = lon

    def get_point(self):
        return Point(self.lon, self.lat)

    def get_info(self):
        return {
            'id': self.id,
            'geometry': self.get_point()
        }


class Objective(GeoObject):
    is_assigned = False

    def get_info(self):
        info = super().get_info()
        info['is_assigned'] = self.is_assigned
        return info


class ObjectiveAllocator:
    """
    :param users: Should be a list of objects of class/subclass `GeoObject` with id of `user_id`
    :param objectives: Should be a list of objects of class/subclass `GeoObject` with id of `case_id`
    :param max_distance: The maximum distance allowed for an objective to be assignable to a user (unit is km)
    :param max_assignable: The maximum number of objectives that can be assigned to a user
    """
    def __init__(self, users, objectives, max_distance, max_assignable):
        if max_distance < 0 or max_assignable < 0:
            raise ValueError("Maximum distance and assignable count must be positive numbers")

        self.users = users
        self.objectives = objectives
        self.max_distance = max_distance
        self.max_assignable = max_assignable

    def _create_dataframe(self, item_list):
        return gpd.GeoDataFrame([item.get_info() for item in item_list]).set_index('id')

    def _get_distance_between_points(self, start_point, end_point):
        """
        Calculate the great circle distance between two points
        on the earth (specified in decimal degrees) using the haversine formula

        Returns the distance between two points rounded to two decimal places, in km
        """
        # Convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [start_point.x, start_point.y, end_point.x, end_point.y])

        # Calculate differences between latitudes and longitudes
        dlon = lon2 - lon1
        dlat = lat2 - lat1

        # Calculate the square of half the chord length between the points
        angular_distance = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2

        # Calculate the central angle between the points
        central_angle = 2 * asin(sqrt(angular_distance))

        EARTH_RADIUS_KM = 6371.0
        distance_km = EARTH_RADIUS_KM * central_angle

        return round(distance_km, 2)

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
            closest_user_geo = gdf.loc[closest_user_id].geometry
            closest_user_dist = self._get_distance_between_points(closest_user_geo, obj_point)

            # If objective is too far for closest user,
            # then no user can access this objective and we'll skip it
            if closest_user_dist > self.max_distance:
                continue

            if closest_user_id not in user_assignment:
                user_assignment[closest_user_id] = []
            user_assignment[closest_user_id].append(obj.id)
            obj.is_assigned = True

            # Remove user from selection if they've hit their assignable limit
            if len(user_assignment[closest_user_id]) == self.max_assignable:
                gdf.drop(closest_user_id, inplace=True)

        return user_assignment
