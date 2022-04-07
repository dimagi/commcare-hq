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
            latitude, longitude, altitude, accuracy = _extract_elements(input_string, flexible)
            return cls(
                _to_decimal(latitude),
                _to_decimal(longitude),
                _to_decimal(altitude),
                _to_decimal(accuracy),
            )
        except _GeoPointGenerationError as e:
            raise BadValueError(f"{input_string} is not a valid format GeoPoint format") from e


def _extract_elements(input_string, flexible):
    try:
        elements = input_string.split(' ')
    except (TypeError, AttributeError, ValueError) as e:
        raise _GeoPointGenerationError(f"{input_string} can't be split") from e

    if len(elements) == 4:
        return elements
    if flexible and len(elements) == 2:
        return elements + ["NaN", "NaN"]
    raise _GeoPointGenerationError(f"Unexpected number of elements: {len(elements)}")


def _to_decimal(n):
    """Coerces to Decimal and rounds small scientific notation inputs to 0"""
    try:
        ret = Decimal(n)
    except InvalidOperation as e:
        raise _GeoPointGenerationError(f"{n} is not a valid Decimal") from e

    uses_sci_notation = 'e' in n.lower()
    if uses_sci_notation and abs(ret) < Decimal("0.001"):
        return Decimal("0")
    return ret


class _GeoPointGenerationError(Exception):
    pass
