from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from corehq.apps.es import case_search_adapter, user_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.data_dictionary.models import CaseType, CaseProperty
from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.tests.utils import create_case
from corehq.form_processor.models import CommCareCase
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.apps.geospatial.views import GeospatialConfigPage, GPSCaptureView
from corehq.apps.geospatial.models import GeoConfig
from corehq.util.test_utils import flag_enabled
from corehq.apps.geospatial.const import GPS_POINT_CASE_PROPERTY


class BaseGeospatialViewClass(TestCase):

    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.username = 'test-user'
        cls.password = '1234'
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

    @property
    def endpoint(self):
        return reverse(self.urlname, args=(self.domain,))


class GeoConfigViewTestClass(TestCase):

    domain = 'test-domain'
    username = 'zeusy'
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

        cls.case_type = CaseType(domain=cls.domain, name='case_type')
        cls.case_type.save()
        cls.gps_case_prop_name = 'gps_prop'
        CaseProperty(
            case_type=cls.case_type,
            name=cls.gps_case_prop_name,
            data_type=CaseProperty.DataType.GPS,
        ).save()

    @classmethod
    def tearDownClass(cls):
        cls.case_type.delete()
        cls.webuser.delete(None, None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def _make_post(self, data):
        self.client.login(username=self.username, password=self.password)
        url = reverse(GeospatialConfigPage.urlname, args=(self.domain,))
        return self.client.post(url, data)

    @staticmethod
    def construct_data(case_property, user_property=None):
        return {
            'case_location_property_name': case_property,
            'user_location_property_name': user_property or '',
        }

    def test_feature_flag_not_enabled(self):
        result = self._make_post({})
        self.assertTrue(result.status_code == 404)

    @flag_enabled('GEOSPATIAL')
    def test_new_config_create(self):
        self.assertEqual(GeoConfig.objects.filter(domain=self.domain).count(), 0)

        self._make_post(
            self.construct_data(
                user_property='some_user_field',
                case_property=self.gps_case_prop_name,
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)

        self.assertTrue(config.location_data_source == GeoConfig.CUSTOM_USER_PROPERTY)
        self.assertEqual(config.user_location_property_name, 'some_user_field')
        self.assertEqual(config.case_location_property_name, self.gps_case_prop_name)

    @flag_enabled('GEOSPATIAL')
    def test_config_update(self):
        self._make_post(
            self.construct_data(
                user_property='some_user_field',
                case_property=self.gps_case_prop_name,
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)
        self.assertEqual(config.user_location_property_name, 'some_user_field')

        self._make_post(
            self.construct_data(
                user_property='some_other_name',
                case_property=config.case_location_property_name,
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)
        self.assertEqual(config.user_location_property_name, 'some_other_name')


class TestGPSCaptureView(BaseGeospatialViewClass):

    urlname = GPSCaptureView.urlname

    def test_no_access(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 404)

        # Logged in but FF not enabled
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 404)

    @flag_enabled('GEOSPATIAL')
    def test_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200)


@flag_enabled('GEOSPATIAL')
@es_test(requires=[case_search_adapter, user_adapter], setup_class=True)
class TestGetPaginatedCasesOrUsers(BaseGeospatialViewClass):

    urlname = 'get_paginated_cases_or_users_without_gps'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        case_type = 'foobar'
        cls.case_a = create_case(
            cls.domain,
            case_id=uuid4().hex,
            case_type=case_type,
            name='CaseA',
            save=True
        )
        cls.case_b = create_case(
            cls.domain,
            case_id=uuid4().hex,
            case_type=case_type,
            name='CaseB',
            case_json={
                GPS_POINT_CASE_PROPERTY: '12.34 45.67',
            },
            save=True,
        )
        case_search_adapter.bulk_index([cls.case_a, cls.case_b], refresh=True)

        cls.user_a = CommCareUser.create(
            cls.domain,
            username='UserA',
            password='1234',
            created_by=None,
            created_via=None,
            metadata={GPS_POINT_CASE_PROPERTY: '12.34 45.67'}
        )
        cls.user_b = CommCareUser.create(
            cls.domain,
            username='UserB',
            password='1234',
            created_by=None,
            created_via=None
        )
        user_adapter.bulk_index([cls.user_a, cls.user_b], refresh=True)

    @classmethod
    def tearDownClass(cls):
        CommCareCase.objects.hard_delete_cases(cls.domain, [
            cls.case_a.case_id,
            cls.case_b.case_id,
        ])
        cls.user_a.delete(cls.domain, None)
        cls.user_b.delete(cls.domain, None)
        super().tearDownClass()

    def test_get_paginated_cases(self):
        expected_output = {
            'total': 1,
            'items': [
                {
                    'id': self.case_a.case_id,
                    'name': self.case_a.name,
                    'lat': '',
                    'lon': '',
                },
            ],
        }
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.endpoint, data={'data_type': 'case', 'limit': 5, 'page': 1})
        self.assertEqual(response.json(), expected_output)

    def test_get_paginated_users_custom_property(self):
        expected_output = {
            'total': 1,
            'items': [
                {
                    'id': self.user_b.user_id,
                    'name': self.user_b.username,
                    'lat': '',
                    'lon': '',
                },
            ],
        }
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.endpoint, data={'data_type': 'user', 'limit': 5, 'page': 1})
        self.assertEqual(response.json(), expected_output)


class TestGetUsersWithGPS(BaseGeospatialViewClass):

    urlname = 'get_users_with_gps'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user_a = CommCareUser.create(
            cls.domain,
            username='UserA',
            password='1234',
            created_by=None,
            created_via=None,
            metadata={GPS_POINT_CASE_PROPERTY: '12.34 45.67'}
        )
        cls.user_b = CommCareUser.create(
            cls.domain,
            username='UserB',
            password='1234',
            created_by=None,
            created_via=None
        )

    @classmethod
    def tearDownClass(cls):
        cls.user_a.delete(cls.domain, None)
        cls.user_b.delete(cls.domain, None)
        super().tearDownClass()

    def test_get_users_with_gps(self):
        expected_output = {
            'user_data': [
                {
                    'id': self.user_a.user_id,
                    'username': self.user_a.raw_username,
                    'gps_point': '12.34 45.67',
                },
                {
                    'id': self.user_b.user_id,
                    'username': self.user_b.raw_username,
                    'gps_point': None,
                },
            ],
        }
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.json(), expected_output)
