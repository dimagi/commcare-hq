from decimal import Decimal

from jsonobject.exceptions import BadValueError
from nose.tools import assert_raises

from ..geopoint import GeoPoint


def test_valid_geopoint_properties():
    for input_string, output in [
        ('42.3739063 -71.1109113 0.0 886.0', ('42.3739063', '-71.1109113', '0.0', '886.0')),
        ('-7.130 -41.563 7.53E-4 8.0', ('-7.130', '-41.563', '0', '8.0')),
        ('-7.130 -41.563 -2.2709742188453674E-4 8.0', ('-7.130', '-41.563', '0', '8.0')),
        ('-7.130 -41.563', ('-7.130', '-41.563', 'NaN', 'NaN')),
        ('-7.130 -41.563 1.2E-3 0', ('-7.130', '-41.563', '0.012', '0')),
    ]:
        actual = GeoPoint.from_string(input_string, flexible=True)
        expected = GeoPoint(*(Decimal(x) for x in output))
    yield _geopoints_equal, actual, expected


def _geopoints_equal(a, b):
    def decimals_equal(x, y):
        # normally Decimal("NaN") != Decimal("NaN")
        return (x.is_nan() and y.is_nan()) or x == y

    return all(
        decimals_equal(getattr(a, field), getattr(b, field))
        for field in ['latitude', 'longitude', 'altitude', 'accuracy']
    )


def test_inflexible_is_strict():
    with assert_raises(BadValueError):
        GeoPoint.from_string('-7.130 -41.563', flexible=False)


def test_invalid_geopoint_properties():
    for input_string in [
            'these are not decimals',
            '42.3739063 -71.1109113 0.0 whoops',
            '42.3739063 -71.1109113 0.0',  # only three elements
    ]:
        yield _is_invalid_input, input_string


def _is_invalid_input(input_string):
    with assert_raises(BadValueError):
        GeoPoint.from_string(input_string)
