from unittest.mock import patch
from uuid import uuid4

from django.http import JsonResponse
from django.test import Client, TestCase
from django.urls import reverse

from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import case_adapter, case_search_adapter, user_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.geospatial.const import ASSIGNED_VIA_DISBURSEMENT_CASE_PROPERTY, GPS_POINT_CASE_PROPERTY
from corehq.apps.geospatial.models import GeoConfig, GeoPolygon
from corehq.apps.geospatial.views import (
    CasesReassignmentView,
    GeoPolygonDetailView,
    GeoPolygonListView,
    GeospatialConfigPage,
    GPSCaptureView,
)
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.form_processor.tests.utils import create_case
from corehq.util.test_utils import flag_enabled


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

    @property
    def login_url(self):
        return reverse('domain_login', kwargs={'domain': self.domain})


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

        cls.min_max_grouping_data = {
            'selected_grouping_method': GeoConfig.MIN_MAX_GROUPING,
            'max_cases_per_group': 10,
            'min_cases_per_group': 5,
            'selected_disbursement_algorithm': GeoConfig.RADIAL_ALGORITHM,
        }
        cls.target_size_grouping_data = {
            'selected_grouping_method': GeoConfig.TARGET_SIZE_GROUPING,
            'target_group_count': 10,
            'selected_disbursement_algorithm': GeoConfig.RADIAL_ALGORITHM,
        }

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
    def construct_data(case_property, user_property=None, extra_data=None):
        data = {
            'case_location_property_name': case_property,
            'user_location_property_name': user_property or '',
            'min_cases_per_user': 1,
            'max_cases_per_user': 2,
            'max_case_distance': 100,
            'max_case_travel_time': 90,
            'travel_mode': 'driving',
        }
        if extra_data:
            data |= extra_data
        return data

    def test_feature_flag_not_enabled(self):
        result = self._make_post({})
        self.assertEqual(result.status_code, 404)

    @flag_enabled('MICROPLANNING')
    def test_new_config_create(self):
        self.assertEqual(GeoConfig.objects.filter(domain=self.domain).count(), 0)

        self._make_post(
            self.construct_data(
                user_property='some_user_field',
                case_property=self.gps_case_prop_name,
                extra_data=self.min_max_grouping_data,
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)

        self.assertEqual(config.location_data_source, GeoConfig.CUSTOM_USER_PROPERTY)
        self.assertEqual(config.user_location_property_name, 'some_user_field')
        self.assertEqual(config.case_location_property_name, self.gps_case_prop_name)
        self.assertEqual(config.selected_grouping_method, GeoConfig.MIN_MAX_GROUPING)
        self.assertEqual(config.max_cases_per_group, 10)
        self.assertEqual(config.min_cases_per_group, 5)
        self.assertEqual(config.selected_disbursement_algorithm, GeoConfig.RADIAL_ALGORITHM)

    @flag_enabled('MICROPLANNING')
    def test_config_update(self):
        self._make_post(
            self.construct_data(
                user_property='some_user_field',
                case_property=self.gps_case_prop_name,
                extra_data=self.min_max_grouping_data,
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)
        self.assertEqual(config.user_location_property_name, 'some_user_field')
        self.assertEqual(config.selected_grouping_method, GeoConfig.MIN_MAX_GROUPING)

        self._make_post(
            self.construct_data(
                user_property='some_other_name',
                case_property=config.case_location_property_name,
                extra_data=self.target_size_grouping_data,
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)
        self.assertEqual(config.user_location_property_name, 'some_other_name')
        self.assertEqual(config.selected_grouping_method, GeoConfig.TARGET_SIZE_GROUPING)
        self.assertEqual(config.target_group_count, 10)
        self.assertEqual(config.selected_disbursement_algorithm, GeoConfig.RADIAL_ALGORITHM)

    @flag_enabled('MICROPLANNING')
    def test_config_update__road_network_algorithm_ff_disabled(self):
        self._make_post(
            self.construct_data(
                case_property='prop1',
                user_property='prop2',
                extra_data={
                    'selected_disbursement_algorithm': GeoConfig.RADIAL_ALGORITHM,
                }
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)
        self.assertEqual(config.selected_disbursement_algorithm, GeoConfig.RADIAL_ALGORITHM)

        self._make_post(
            self.construct_data(
                case_property='prop1',
                user_property='prop2',
                extra_data={
                    'selected_disbursement_algorithm': GeoConfig.ROAD_NETWORK_ALGORITHM
                },
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)
        self.assertEqual(config.selected_disbursement_algorithm, GeoConfig.RADIAL_ALGORITHM)

    @flag_enabled('MICROPLANNING')
    @flag_enabled('SUPPORT_ROAD_NETWORK_DISBURSEMENT_ALGORITHM')
    def test_config_update__road_network_algorithm_ff_enabled(self):
        self._make_post(
            self.construct_data(
                case_property='prop1',
                user_property='prop2',
                extra_data={
                    'selected_disbursement_algorithm': GeoConfig.RADIAL_ALGORITHM,
                }
            )
        )
        config = GeoConfig.objects.get(domain=self.domain)
        self.assertEqual(config.selected_disbursement_algorithm, GeoConfig.RADIAL_ALGORITHM)


@es_test(requires=[case_adapter], setup_class=True)
class TestGPSCaptureView(BaseGeospatialViewClass):
    urlname = GPSCaptureView.urlname

    def test_no_access(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 404)

        # Logged in but FF not enabled
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 404)

    @flag_enabled('MICROPLANNING')
    def test_success(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200)


@flag_enabled('MICROPLANNING')
@es_test(requires=[case_search_adapter, user_adapter], setup_class=True)
class TestGetPaginatedCasesOrUsers(BaseGeospatialViewClass):
    urlname = 'get_paginated_cases_or_users'

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
            user_data={GPS_POINT_CASE_PROPERTY: '12.34 45.67'}
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


@es_test(requires=[user_adapter], setup_class=True)
class TestGetUsersWithGPS(BaseGeospatialViewClass):
    urlname = 'get_users_with_gps'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.location_type = LocationType.objects.create(
            domain=cls.domain,
            name='country',
        )
        cls.country_a = SQLLocation.objects.create(
            domain=cls.domain,
            name='Country A',
            location_type=cls.location_type,
        )
        cls.country_b = SQLLocation.objects.create(
            domain=cls.domain,
            name='Country B',
            location_type=cls.location_type,
        )

        cls.user_a = CommCareUser.create(
            cls.domain,
            username='UserA',
            password='1234',
            created_by=None,
            created_via=None,
            user_data={GPS_POINT_CASE_PROPERTY: '12.34 45.67'},
            location=cls.country_a,
        )
        cls.user_b = CommCareUser.create(
            cls.domain,
            username='UserB',
            password='1234',
            created_by=None,
            created_via=None,
            location=cls.country_b,
        )
        cls.user_c = CommCareUser.create(
            cls.domain,
            username='UserC',
            password='1234',
            created_by=None,
            created_via=None,
            user_data={GPS_POINT_CASE_PROPERTY: '45.67 12.34'},
        )

        user_adapter.bulk_index([cls.user_a, cls.user_b, cls.user_c], refresh=True)

    @classmethod
    def tearDownClass(cls):
        for user in CommCareUser.by_domain(cls.domain):
            user.delete(cls.domain, None)
        for location in SQLLocation.objects.filter(domain=cls.domain):
            location.delete()
        cls.location_type.delete()
        super().tearDownClass()

    def test_get_users_with_gps(self):
        expected_results = {
            self.user_a.user_id: {
                'id': self.user_a.user_id,
                'username': self.user_a.raw_username,
                'gps_point': '12.34 45.67',
                'primary_loc_name': self.country_a.name,
            },
            self.user_c.user_id: {
                'id': self.user_c.user_id,
                'username': self.user_c.raw_username,
                'gps_point': '45.67 12.34',
                'primary_loc_name': '---',
            }
        }
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.endpoint)
        response_json = response.json()
        self.assertIn('user_data', response_json)
        user_data = {user['id']: user for user in response_json['user_data']}
        self.assertEqual(user_data, expected_results)

    def test_get_location_filtered_users(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.endpoint, data={'location_id': self.country_a.location_id})
        user_data = response.json()['user_data']
        self.assertEqual(len(user_data), 1)
        self.assertEqual(user_data[0]['gps_point'], '12.34 45.67')


class TestGeoPolygonListView(BaseGeospatialViewClass):
    urlname = GeoPolygonListView.urlname

    def setUp(self):
        super().setUp()
        self.client.login(username=self.username, password=self.password)

    def tearDown(self):
        GeoPolygon.objects.all().delete()
        super().tearDown()

    def _make_post_request(self, data):
        return self.client.post(
            self.endpoint,
            data=data,
            content_type='application/json',
        )

    @flag_enabled('MICROPLANNING')
    def test_not_logged_in(self):
        response = Client().post(self.endpoint, _sample_geojson_data())
        self.assertRedirects(response, f"{self.login_url}?next={self.endpoint}")

    def test_feature_flag_not_enabled(self):
        response = self._make_post_request({'geo_json': _sample_geojson_data()})
        self.assertEqual(response.status_code, 404)

    @flag_enabled('MICROPLANNING')
    def test_save_polygon(self):
        geo_json_data = _sample_geojson_data()
        response = self._make_post_request({'geo_json': geo_json_data})
        self.assertEqual(response.status_code, 200)
        saved_polygons = GeoPolygon.objects.filter(domain=self.domain)
        self.assertEqual(len(saved_polygons), 1)
        self.assertEqual(saved_polygons[0].name, geo_json_data["name"])
        geo_json_data.pop("name")
        for feature in geo_json_data["features"]:
            del feature['id']
        self.assertEqual(saved_polygons[0].geo_json, geo_json_data)

    def _assert_error_message(self, response, message):
        error = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(error, message,)

    @flag_enabled('MICROPLANNING')
    def test_geo_json_validation(self):
        response = self.client.generic('POST', self.endpoint, 'foobar')
        self._assert_error_message(
            response,
            message='POST Body must be a valid json in {"geo_json": <geo_json>} format'
        )
        response = self._make_post_request({'foo': 'bar'})
        self._assert_error_message(
            response,
            message='Empty geo_json POST field'
        )
        response = self._make_post_request({'geo_json': {'foo': 'bar'}})
        self._assert_error_message(
            response,
            message='Invalid GeoJSON, geo_json must be a FeatureCollection of Polygons'
        )

    @flag_enabled('MICROPLANNING')
    def test_empty_name_validation(self):
        response = self._make_post_request({'geo_json': _sample_geojson_data(name='')})
        self._assert_error_message(
            response,
            message='Please specify a name for the GeoPolygon area.'
        )

    @flag_enabled('MICROPLANNING')
    def test_name_validation(self):
        GeoPolygon.objects.create(
            domain=self.domain,
            geo_json={},
            name='foobar',
        )
        response = self._make_post_request({'geo_json': _sample_geojson_data(name='FooBAR')})
        self._assert_error_message(
            response,
            message='GeoPolygon with given name already exists! Please use a different name.'
        )


class TestGeoPolygonDetailView(BaseGeospatialViewClass):
    urlname = GeoPolygonDetailView.urlname

    def setUp(self):
        super().setUp()
        self.client.login(username=self.username, password=self.password)

    def tearDown(self):
        GeoPolygon.objects.all().delete()
        super().tearDown()

    def _create_sample_polygon(self):
        geo_json_data = _sample_geojson_data()
        return GeoPolygon.objects.create(
            name=geo_json_data.pop('name'),
            domain=self.domain,
            geo_json=geo_json_data
        )

    def _endpoint(self, geo_polygon_id):
        return reverse(GeoPolygonDetailView.urlname, kwargs={"domain": self.domain, "pk": geo_polygon_id})

    @flag_enabled('MICROPLANNING')
    def test_not_logged_in(self):
        geo_polygon = self._create_sample_polygon()
        response = Client().get(self._endpoint(geo_polygon.id))
        self.assertRedirects(response, f"{self.login_url}?next={self._endpoint(geo_polygon.id)}")

    def test_feature_flag_not_enabled(self):
        geo_polygon = self._create_sample_polygon()
        response = self.client.get(self._endpoint(geo_polygon.id))
        self.assertEqual(response.status_code, 404)

    @flag_enabled('MICROPLANNING')
    def test_get_polygon(self):
        geo_polygon = self._create_sample_polygon()
        response = self.client.get(self._endpoint(geo_polygon.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), geo_polygon.geo_json)

    @flag_enabled('MICROPLANNING')
    def test_delete_polygon(self):
        geo_polygon = self._create_sample_polygon()
        response = self.client.delete(self._endpoint(geo_polygon.id))
        self.assertEqual(response.status_code, 200)
        with self.assertRaises(GeoPolygon.DoesNotExist):
            GeoPolygon.objects.get(pk=geo_polygon.id, domain=self.domain)
        saved_polygons = GeoPolygon.objects.filter(domain=self.domain)
        self.assertEqual(len(saved_polygons), 0)


def _sample_geojson_data(name='test-2'):
    data = {
        "type": "FeatureCollection",
        "features": [
            {
                "id": "5af4923d29d0669052ed15737fcd9627",
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "coordinates": [
                        [
                            [2.8405520338592964, 10.123570736635216],
                            [2.9854525080494057, 9.603842241835679],
                            [3.857119423099789, 9.98535424153846],
                            [3.601279523358272, 10.2973713850877],
                            [2.601279523358272, 10.123570736635216],
                        ]
                    ],
                    "type": "Polygon"
                }
            }
        ],
        "name": name,
    }
    return data


@es_test(requires=[case_search_adapter, user_adapter])
class TestCasesReassignmentView(BaseGeospatialViewClass):
    urlname = CasesReassignmentView.urlname

    def setUp(self):
        super().setUp()
        self.user_a = CommCareUser.create(self.domain, 'User_A', '1234', None, None)
        self.user_b = CommCareUser.create(self.domain, 'User_B', '1234', None, None)
        user_adapter.bulk_index([self.user_a, self.user_b], refresh=True)

        self.case_1 = create_case(self.domain, case_id=uuid4().hex, save=True, owner_id=self.user_a.user_id)
        self.related_case_1 = create_case(
            self.domain,
            case_id=uuid4().hex,
            save=True,
            owner_id=self.user_a.user_id
        )
        self._create_parent_index(self.related_case_1, self.case_1.case_id)

        self.case_2 = create_case(
            self.domain,
            case_id=uuid4().hex,
            save=True,
            owner_id=self.user_b.user_id
        )
        self.related_case_2 = create_case(
            self.domain,
            case_id=uuid4().hex,
            save=True,
            owner_id=self.user_b.user_id
        )
        self._create_parent_index(self.related_case_2, self.case_2.case_id)

        self.cases = [self.case_1, self.related_case_1, self.case_2, self.related_case_2]
        case_search_adapter.bulk_index(self.cases, refresh=True)

        self.client.login(username=self.username, password=self.password)

    def tearDown(self):
        self.user_a.delete(self.domain, None, None)
        self.user_b.delete(self.domain, None, None)
        CommCareCase.objects.hard_delete_cases(self.domain, [case.case_id for case in self.cases])
        super().tearDown()

    def _create_parent_index(self, case, parent_case_id):
        index = CommCareCaseIndex(
            case=case,
            identifier='parent',
            referenced_id=parent_case_id,
            referenced_type='parent',
            relationship_id=CommCareCaseIndex.CHILD
        )
        case.track_create(index)
        case.save(with_tracked_models=True)

    def _refresh_cases(self):
        for case in self.cases:
            case.refresh_from_db()

    def _assert_for_request_cases_success(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.case_1.owner_id, self.user_b.user_id)
        self.assertEqual(self.case_2.owner_id, self.user_a.user_id)

    @flag_enabled('MICROPLANNING')
    def test_not_logged_in(self):
        response = Client().post(self.endpoint)
        self.assertRedirects(response, f"{self.login_url}?next={self.endpoint}")

    def test_feature_flag_not_enabled(self):
        response = self.client.post(self.endpoint)
        self.assertEqual(response.status_code, 404)

    def _assert_for_assigned_cases_flag_disabled(self, cases):
        for case in cases:
            self.assertIsNone(case.case_json.get(ASSIGNED_VIA_DISBURSEMENT_CASE_PROPERTY))

    def _assert_for_assigned_cases_flag_enabled(self, cases):
        for case in cases:
            self.assertTrue(case.case_json.get(ASSIGNED_VIA_DISBURSEMENT_CASE_PROPERTY))

    @flag_enabled('MICROPLANNING')
    def test_cases_reassignment(self):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: self.user_a.user_id,
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
            }
        )

        self._refresh_cases()
        self._assert_for_request_cases_success(response)
        self.assertEqual(self.related_case_1.owner_id, self.user_a.user_id)
        self.assertEqual(self.related_case_2.owner_id, self.user_b.user_id)
        self._assert_for_assigned_cases_flag_disabled([self.case_1, self.case_2])

    @flag_enabled('MICROPLANNING')
    @patch('corehq.apps.geospatial.views.get_flag_assigned_cases_config', return_value=True)
    def test_cases_reassignment_with_assigned_cases_flag_enabled(self, *args):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: self.user_a.user_id,
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
            }
        )

        self._refresh_cases()
        self._assert_for_request_cases_success(response)
        self.assertEqual(self.related_case_1.owner_id, self.user_a.user_id)
        self.assertEqual(self.related_case_2.owner_id, self.user_b.user_id)
        self._assert_for_assigned_cases_flag_enabled([self.case_1, self.case_2])

    @flag_enabled('MICROPLANNING')
    def test_cases_reassignment_with_related_cases(self):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: self.user_a.user_id,
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
                'include_related_cases': True,
            }
        )

        self._refresh_cases()
        self._assert_for_request_cases_success(response)
        self.assertEqual(self.related_case_1.owner_id, self.user_b.user_id)
        self.assertEqual(self.related_case_2.owner_id, self.user_a.user_id)
        self._assert_for_assigned_cases_flag_disabled(
            [self.case_1, self.case_2, self.related_case_1, self.related_case_2]
        )

    @flag_enabled('MICROPLANNING')
    @patch('corehq.apps.geospatial.views.get_flag_assigned_cases_config', return_value=True)
    def test_cases_reassignment_with_related_cases_and_assigned_cases_flag_enabled(self, *args):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: self.user_a.user_id,
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
                'include_related_cases': True,
            }
        )

        self._refresh_cases()
        self._assert_for_request_cases_success(response)
        self.assertEqual(self.related_case_1.owner_id, self.user_b.user_id)
        self.assertEqual(self.related_case_2.owner_id, self.user_a.user_id)
        self._assert_for_assigned_cases_flag_enabled(
            [self.case_1, self.case_2, self.related_case_1, self.related_case_2]
        )

    @flag_enabled('MICROPLANNING')
    def test_cases_reassignment_with_related_case_in_request(self):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: self.user_a.user_id,
            self.related_case_1.case_id: self.user_a.user_id,
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
                'include_related_cases': True,
            }
        )

        self._refresh_cases()
        self._assert_for_request_cases_success(response)
        self.assertEqual(self.related_case_1.owner_id, self.user_a.user_id)
        self.assertEqual(self.related_case_2.owner_id, self.user_a.user_id)

    @flag_enabled('MICROPLANNING')
    @patch('corehq.apps.geospatial.views.CasesReassignmentView.REQUEST_CASES_LIMIT', 1)
    def test_cases_reassignment_cases_limit_error(self, *args):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: self.user_a.user_id,
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode("utf-8"), "Maximum number of cases that can be reassigned is 1")

    @flag_enabled('MICROPLANNING')
    def test_cases_reassignment_cases_json_error(self, *args):
        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data='hello'
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode("utf-8"), "POST Body must be a valid json")

    @flag_enabled('MICROPLANNING')
    def test_cases_reassignment_cases_invalid_case_ids(self, *args):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            'invalid-case-id': self.user_a.user_id,
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.content.decode("utf-8"),
            "Following Case ids in request are invalid: {}".format(['invalid-case-id'])
        )

    @flag_enabled('MICROPLANNING')
    def test_cases_reassignment_cases_invalid_owner_ids(self, *args):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: 'invalid-owner-id',
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.content.decode("utf-8"),
            "Following Owner ids in request are invalid: {}".format(['invalid-owner-id'])
        )

    @flag_enabled('MICROPLANNING')
    @patch('corehq.apps.geospatial.views.CasesReassignmentView.ASYNC_CASES_UPDATE_THRESHOLD', 2)
    @patch('corehq.apps.geospatial.views.CasesReassignmentView._process_as_async')
    def test_cases_reassignment_async_invocation(self, mocked_process_as_async):
        mocked_process_as_async.return_value = JsonResponse({})
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: self.user_a.user_id,
        }

        self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
                'include_related_cases': True,
            }
        )
        mocked_process_as_async.assert_called_once()

    @flag_enabled('MICROPLANNING')
    @patch('corehq.apps.geospatial.views.CasesReassignmentView.ASYNC_CASES_UPDATE_THRESHOLD', 2)
    @patch('corehq.apps.geospatial.views.CeleryTaskTracker.is_active', return_value=False)
    def test_cases_reassignment_async(self, *args):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: self.user_a.user_id,
            self.related_case_1.case_id: self.user_a.user_id,
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
            }
        )
        self._refresh_cases()
        self._assert_for_request_cases_success(response)
        self.assertEqual(self.related_case_1.owner_id, self.user_a.user_id)
        self.assertEqual(self.related_case_2.owner_id, self.user_b.user_id)
        self._assert_for_assigned_cases_flag_disabled([self.case_1, self.case_2, self.related_case_1])

    @flag_enabled('MICROPLANNING')
    @patch('corehq.apps.geospatial.tasks.get_flag_assigned_cases_config', return_value=True)
    @patch('corehq.apps.geospatial.views.CasesReassignmentView.ASYNC_CASES_UPDATE_THRESHOLD', 2)
    @patch('corehq.apps.geospatial.views.CeleryTaskTracker.is_active', return_value=False)
    def test_cases_reassignment_async_with_assigned_cases_flag_enabled(self, *args):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: self.user_a.user_id,
            self.related_case_1.case_id: self.user_a.user_id,
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
            }
        )
        self._refresh_cases()
        self._assert_for_request_cases_success(response)
        self.assertEqual(self.related_case_1.owner_id, self.user_a.user_id)
        self.assertEqual(self.related_case_2.owner_id, self.user_b.user_id)
        self._assert_for_assigned_cases_flag_enabled([self.case_1, self.case_2, self.related_case_1])

    @flag_enabled('MICROPLANNING')
    @patch('corehq.apps.geospatial.views.CasesReassignmentView.ASYNC_CASES_UPDATE_THRESHOLD', 2)
    @patch('corehq.apps.geospatial.views.CeleryTaskTracker.is_active', return_value=True)
    def test_cases_reassignment_async_task_invoked_and_not_completed(self, *args):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: self.user_a.user_id,
            self.related_case_1.case_id: self.user_a.user_id,
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
            }
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.content.decode("utf-8"),
            "Case reassignment is currently in progress. Please try again later."
        )

    @flag_enabled('MICROPLANNING')
    @patch('corehq.apps.geospatial.views.CasesReassignmentView.TOTAL_CASES_LIMIT', 3)
    def test_cases_reassignment_max_limit_error(self):
        case_id_to_owner_id = {
            self.case_1.case_id: self.user_b.user_id,
            self.case_2.case_id: self.user_a.user_id,
        }

        response = self.client.post(
            self.endpoint,
            content_type='application/json',
            data={
                'case_id_to_owner_id': case_id_to_owner_id,
                'include_related_cases': True,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.content.decode("utf-8"),
            ("Case reassignment limit exceeded. Please select fewer cases to update"
             " or consider deselecting 'include related cases'."
             " Reach out to support if you still need assistance.")
        )
