from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.apps.geospatial.views import GeospatialConfigPage
from corehq.apps.geospatial.models import GeoConfig
from corehq.util.test_utils import flag_enabled
from corehq.apps.geospatial.const import GEO_POINT_CASE_PROPERTY


class GeoConfigViewTestClass(TestCase):

    domain = 'test-domain'
    username = 'zeus'
    password = 'nyx'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.webuser = WebUser.create(
            cls.domain,
            cls.username,
            cls.password,
            None,
            None,
            is_admin=True,
        )
        cls.webuser.save()

    @classmethod
    def tearDownClass(cls):
        cls.webuser.delete(None, None)
        cls.domain_obj.delete()

        super().tearDownClass()

    def _make_post(self, data):
        self.client.login(username=self.username, password=self.password)
        url = reverse(GeospatialConfigPage.urlname, args=(self.domain,))
        return self.client.post(url, data)

    @staticmethod
    def construct_data(source, case_property, user_property=None):
        return {
            'location_source_option': source,
            'geo_case_property_name': case_property,
            'custom_user_field_name': user_property or '',
        }

    def test_feature_flag_not_enabled(self):
        result = self._make_post({})
        self.assertTrue(result.status_code == 404)

    @flag_enabled('GEOSPATIAL')
    def test_new_config_create(self):
        self.assertEqual(GeoConfig.objects.filter(domain=self.domain).count(), 0)

        self._make_post(
            self.construct_data(
                source=GeoConfig.CUSTOM_USER_PROPERTY,
                user_property='some_user_field',
                case_property='some_case_prop',
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)

        self.assertTrue(config.location_data_source == GeoConfig.CUSTOM_USER_PROPERTY)
        self.assertEqual(config.user_location_property_name, 'some_user_field')
        self.assertEqual(config.case_location_property_name, 'some_case_prop')

    @flag_enabled('GEOSPATIAL')
    def test_new_config_create_with_default_values(self):
        self._make_post(
            self.construct_data(
                source=GeoConfig.ASSIGNED_LOCATION,
                case_property='some_case_prop',
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)

        self.assertTrue(config.location_data_source == GeoConfig.ASSIGNED_LOCATION)
        self.assertEqual(config.user_location_property_name, GEO_POINT_CASE_PROPERTY)

    @flag_enabled('GEOSPATIAL')
    def test_config_update(self):
        self._make_post(
            self.construct_data(
                source=GeoConfig.CUSTOM_USER_PROPERTY,
                user_property='some_user_field',
                case_property='some_case_prop',
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)
        self.assertEqual(config.user_location_property_name, 'some_user_field')

        self._make_post(
            self.construct_data(
                source=config.location_data_source,
                user_property='some_other_name',
                case_property=config.case_location_property_name,
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)
        self.assertEqual(config.user_location_property_name, 'some_other_name')

    @flag_enabled('GEOSPATIAL')
    def test_config_update_does_not_update_user_prop(self):
        self._make_post(
            self.construct_data(
                source=GeoConfig.CUSTOM_USER_PROPERTY,
                user_property='original_field_name',
                case_property='some_case_prop',
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)
        self.assertEqual(config.user_location_property_name, 'original_field_name')

        self._make_post(
            self.construct_data(
                source=GeoConfig.ASSIGNED_LOCATION,
                user_property='other_field_name',
                case_property=config.case_location_property_name,
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)
        self.assertEqual(config.user_location_property_name, 'original_field_name')
