from __future__ import absolute_import
from __future__ import unicode_literals
from decimal import Decimal, InvalidOperation
from jsonobject.base_properties import JsonProperty
from jsonobject.exceptions import BadValueError
import re
from .datatypes import GeoPoint
import six


def _canonical_decimal(n):
    """
    raises ValueError for non-canonically formatted decimal strings

    example: '00.1' or '.1' whose canonical form is '0.1'

    """
    value_error = False
    try:
        decimal = Decimal(n)
    except InvalidOperation:
        value_error = True
    if value_error:
        raise ValueError('{!r} is not a canonically formatted decimal'
                         .format(n))
    return decimal


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


class GeoPointProperty(JsonProperty):
    """
    wraps a GeoPoint object where the numbers are represented as Decimals
    to preserve exact formatting (number of decimal places, etc.)

    # Test normal
    >>> GeoPointProperty().wrap('42.3739063 -71.1109113 0.0 886.0')
    GeoPoint(latitude=Decimal('42.3739063'), longitude=Decimal('-71.1109113'),
             altitude=Decimal('0.0'), accuracy=Decimal('886.0'))

    # Test scientific notation hack
    >>> GeoPointProperty().wrap('-7.130 -41.563 7.53E-4 8.0')
    GeoPoint(latitude=Decimal('-7.130'), longitude=Decimal('-41.563'),
             altitude=Decimal('0'), accuracy=Decimal('8.0'))

    >>> GeoPointProperty().wrap('-7.130 -41.563 -2.2709742188453674E-4 8.0')
    GeoPoint(latitude=Decimal('-7.130'), longitude=Decimal('-41.563'),
             altitude=Decimal('0'), accuracy=Decimal('8.0'))

    """

    def wrap(self, obj):
        try:
            latitude, longitude, altitude, accuracy = obj.split(' ')
        except (TypeError, AttributeError, ValueError):
            raise BadValueError("GeoPoint format expects 4 decimals: {!r}"
                                .format(obj))
        try:
            # this should eventually be removed once it's fixed on the mobile
            # the mobile sometimes submits in scientific notation
            # but only comes up for very small values
            # http://manage.dimagi.com/default.asp?159863
            latitude = _canonical_decimal_round_tiny_exp(latitude)
            longitude = _canonical_decimal_round_tiny_exp(longitude)
            altitude = _canonical_decimal_round_tiny_exp(altitude)
            accuracy = _canonical_decimal_round_tiny_exp(accuracy)
        except ValueError:
            raise BadValueError("{!r} is not a valid format GeoPoint format"
                                .format(obj))
        return GeoPoint(latitude, longitude, altitude, accuracy)

    def unwrap(self, obj):
        return obj, '{} {} {} {}'.format(*obj)
