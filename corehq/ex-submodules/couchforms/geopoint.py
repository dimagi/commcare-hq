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
            # this should eventually be removed once it's fixed on the mobile
            # the mobile sometimes submits in scientific notation
            # but only comes up for very small values
            # http://manage.dimagi.com/default.asp?159863
            latitude = _canonical_decimal_round_tiny_exp(latitude)
            longitude = _canonical_decimal_round_tiny_exp(longitude)
            altitude = _canonical_decimal_round_tiny_exp(altitude)
            accuracy = _canonical_decimal_round_tiny_exp(accuracy)
        except ValueError as e:
            raise BadValueError("{!r} is not a valid format GeoPoint format"
                                .format(input_string)) from e
        return cls(latitude, longitude, altitude, accuracy)


def _canonical_decimal(n):
    """
    raises ValueError for non-canonically formatted decimal strings

    example: '00.1' or '.1' whose canonical form is '0.1'

    """
    try:
        return Decimal(n)
    except InvalidOperation:
        raise ValueError('{!r} is not a canonically formatted decimal'
                         .format(n))


def _canonical_decimal_round_tiny_exp(n):
    """
    Same behavior as _canonical_decimal, but also accepts small values in
    scientific notation, rounding them to zero

    """
    exp_match = re.match(r'^-?\d.\d+E-(\d)$', n)
    if exp_match:
        e = int(exp_match.group(1))
        if e < 4:
            raise ValueError('Hack for scientific notation only works for '
                             'negative exponents 4 and above: {!r}'.format(n))
        else:
            return Decimal('0')
    else:
        return _canonical_decimal(n)
