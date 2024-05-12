from contextlib import contextmanager

from django.test import TestCase

from ..const import GPS_POINT_CASE_PROPERTY, ALGO_AES
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

    def test_geo_config_api_token(self):
        with self.get_geo_config() as config:
            config.plaintext_api_token = '1234'
            self.assertEqual(config.plaintext_api_token, '1234')
            self.assertTrue(config.api_token.startswith(f"${ALGO_AES}$"))

            config.plaintext_api_token = None
            self.assertEqual(config.plaintext_api_token, None)
            self.assertEqual(config.api_token, None)

    def test_geo_config_api_token_cannot_be_non_str(self):
        with self.assertRaises(AssertionError) as context:
            with self.get_geo_config() as config:
                config.plaintext_api_token = 1234

        self.assertEqual(str(context.exception), "Only string values allowed for api token")

    def test_geo_config_api_token_cannot_be_empty(self):
        with self.assertRaises(Exception) as context:
            with self.get_geo_config() as config:
                config.plaintext_api_token = ""

        self.assertEqual(str(context.exception), "Unexpected value set for plaintext api token")

    def test_geo_config_api_token_cannot_start_with_encryption_str(self):
        with self.assertRaises(Exception) as context:
            with self.get_geo_config() as config:
                config.plaintext_api_token = f"${ALGO_AES}$1234"

        self.assertEqual(str(context.exception), "Unexpected value set for plaintext api token")

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
