import re
from collections import namedtuple
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from jsonobject.exceptions import BadValueError


@dataclass(frozen=True)
class GeoPoint:
    latitude: Decimal
    longitude: Decimal
    altitude: Decimal
    accuracy: Decimal

    @property
    def lat_lon(self):
        """Suitable to send to an elasticsearch geo_point field"""
        return {
            'lat': self.latitude,
            'lon': self.longitude
        }

    @classmethod
    def from_string(cls, input_string, flexible=False):
        """
        Construct GeoPoint object from string containing space-separated decimals.

        Expects 4 elements, unless flexible=True, in which case 2 works too
        """
        try:
            elements = input_string.split(' ')
            if len(elements) == 4:
                latitude, longitude, altitude, accuracy = elements
            elif flexible and len(elements) == 2:
                latitude, longitude = elements
                altitude, accuracy = "NaN", "NaN"
            else:
                raise ValueError(f"Unexpected number of elements: {len(elements)}")
        except (TypeError, AttributeError, ValueError) as e:
            raise BadValueError("GeoPoint format expects 4 decimals: {!r}"
                                .format(input_string)) from e
        try:
            latitude = _to_decimal(latitude)
            longitude = _to_decimal(longitude)
            altitude = _to_decimal(altitude)
            accuracy = _to_decimal(accuracy)
        except ValueError as e:
            raise BadValueError("{!r} is not a valid format GeoPoint format"
                                .format(input_string)) from e
        return cls(latitude, longitude, altitude, accuracy)


def _to_decimal(n):
    try:
        ret = Decimal(n)
    except InvalidOperation:
        raise ValueError(f"{n} is not a valid Decimal")
    if not ret.is_nan() and abs(ret) < Decimal("0.001"):
        return Decimal("0")
    return ret
