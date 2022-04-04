from decimal import Decimal

from nose.tools import assert_equal

from ..geopoint import GeoPoint


def test_valid_geopoint_properties():
    for input_string, output in [
        ('42.3739063 -71.1109113 0.0 886.0', ('42.3739063', '-71.1109113', '0.0', '886.0')),
        ('-7.130 -41.563 7.53E-4 8.0', ('-7.130', '-41.563', '0', '8.0')),
        ('-7.130 -41.563 -2.2709742188453674E-4 8.0', ('-7.130', '-41.563', '0', '8.0')),
    ]:
        actual = GeoPoint.from_string(input_string)
        expected = GeoPoint(*(Decimal(x) for x in output))
    yield assert_equal, actual, expected
