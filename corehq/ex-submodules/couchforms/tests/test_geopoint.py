from decimal import Decimal

from jsonobject.exceptions import BadValueError
from nose.tools import assert_equal, assert_raises

from ..geopoint import GeoPoint


def test_valid_geopoint_properties():
    for input_string, output in [
        ('42.3739063 -71.1109113 0.0 886.0', ('42.3739063', '-71.1109113', '0.0', '886.0')),
        ('-7.130 -41.563 7.53E-4 8.0', ('-7.130', '-41.563', '0', '8.0')),
        ('-7.130 -41.563 -2.2709742188453674E-4 8.0', ('-7.130', '-41.563', '0', '8.0')),
        ('-7.130 -41.563', ('-7.130', '-41.563', 'NaN', 'NaN')),
        ('-7.130 -41.563 1.2E-3 0', ('-7.130', '-41.563', '0.012', '0')),
        ('-7.130 -41.563 0.0 1.0', ('-7.130', '-41.563', '0.0', '1.0')),
    ]:
        actual = GeoPoint.from_string(input_string, flexible=True)
        expected = GeoPoint(*(Decimal(x) for x in output))
    yield _geopoints_equal, actual, expected


def _geopoints_equal(a, b):
    for field in ['latitude', 'longitude', 'altitude', 'accuracy']:
        assert_equal(str(getattr(a, field)), str(getattr(b, field)))


def test_inflexible_is_strict():
    with assert_raises(BadValueError):
        GeoPoint.from_string('-7.130 -41.563', flexible=False)


def test_invalid_geopoint_properties():
    for input_string in [
            'these are not decimals',
            '42.3739063 -71.1109113 0.0 whoops',
            '42.3739063 -71.1109113 0.0',  # only three elements
            3,  # wrong type
            '24.85676533097921 240.27256620218806 0.0 0.0',  # out of bounds
            '-11.683438999546881 -184.6692769950829 0.0 0.0',  # out of bounds
            'NaN -71.669 0.0 0.0',
    ]:
        yield _is_invalid_input, input_string


def _is_invalid_input(input_string):
    with assert_raises(BadValueError):
        GeoPoint.from_string(input_string)
