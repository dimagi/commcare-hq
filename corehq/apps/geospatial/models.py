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
