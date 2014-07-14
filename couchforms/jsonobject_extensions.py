from decimal import Decimal
from jsonobject import JsonProperty
from jsonobject.exceptions import BadValueError
from .datatypes import GeoPoint


def _canonical_decimal(n):
    """
    raises ValueError for non-canonically formatted decimal strings

    example: '00.1' or '.1' whose canonical form is '0.1'

    """
    decimal = Decimal(n)
    if unicode(decimal) != n:
        raise ValueError('{!r} is not a canonically formatted decimal')
    return decimal


class GeoPointProperty(JsonProperty):
    """
    wraps a GeoPoint object where the numbers are represented as Decimals
    to preserve exact formatting (number of decimal places, etc.)

    """

    def wrap(self, obj):
        try:
            return GeoPoint(*[_canonical_decimal(n) for n in obj.split(' ')])
        except (ValueError, TypeError):
            raise BadValueError("{!r} is not a valid format GeoPoint format"
                                .format(obj))

    def unwrap(self, obj):
        return obj, '{} {} {} {}'.format(*obj)
