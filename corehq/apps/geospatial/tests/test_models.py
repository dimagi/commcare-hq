from contextlib import contextmanager

from django.test import TestCase

from ..const import GPS_POINT_CASE_PROPERTY
from ..models import GeoConfig
from ..utils import get_geo_case_property


class TestGeoConfig(TestCase):

    domain = 'test-geo-config'
    geo_property = 'gps_location'

    def test_geo_config(self):
        case_property = get_geo_case_property(self.domain)
        self.assertEqual(case_property, GPS_POINT_CASE_PROPERTY)
        with self.get_geo_config():
            case_property = get_geo_case_property(self.domain)
            self.assertEqual(case_property, self.geo_property)
        case_property = get_geo_case_property(self.domain)
        self.assertEqual(case_property, GPS_POINT_CASE_PROPERTY)

    @contextmanager
    def get_geo_config(self):
        conf = GeoConfig(
            domain=self.domain,
            case_location_property_name=self.geo_property,
        )
        conf.save()
        try:
            yield conf
        finally:
            conf.delete()
