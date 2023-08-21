from django.test import TestCase
from corehq.apps.geospatial.models import GeoConfig
from corehq.apps.geospatial.utils import get_geo_case_property
from corehq.apps.geospatial.const import GEO_POINT_CASE_PROPERTY


class TestGetGeoCaseProperty(TestCase):

    DOMAIN = "test-domain"

    def test_no_config_set(self):
        self.assertEqual(get_geo_case_property(self.DOMAIN), GEO_POINT_CASE_PROPERTY)

    def custom_config_set(self):
        geo_property = "where-art-thou"

        GeoConfig(domain=self.DOMAIN, case_location_property_name=geo_property).save()
        self.assertEqual(get_geo_case_property(self.DOMAIN), geo_property)

    def test_invalid_domain_provided(self):
        self.assertEqual(get_geo_case_property(None), GEO_POINT_CASE_PROPERTY)
