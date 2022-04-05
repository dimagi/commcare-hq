from jsonobject.base_properties import JsonProperty
from .geopoint import GeoPoint


class GeoPointProperty(JsonProperty):
    """
    wraps a GeoPoint object where the numbers are represented as Decimals
    to preserve exact formatting (number of decimal places, etc.)
    """

    def wrap(self, obj):
        return GeoPoint.from_string(obj)

    def unwrap(self, obj):
        return obj, f"{obj.latitude} {obj.longitude} {obj.altitude} {obj.accuracy}"
