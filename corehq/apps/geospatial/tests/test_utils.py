from uuid import uuid4

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import create_case
from corehq.apps.geospatial.models import GeoConfig
from corehq.apps.geospatial.utils import (
    get_geo_case_property,
    get_geo_user_property,
    set_case_gps_property,
    set_user_gps_property,
    create_case_with_gps_property,
)
from corehq.apps.geospatial.const import GPS_POINT_CASE_PROPERTY


class TestGetGeoProperty(TestCase):

    DOMAIN = "test-domain"

    def test_no_config_set(self):
        self.assertEqual(get_geo_case_property(self.DOMAIN), GPS_POINT_CASE_PROPERTY)
        self.assertEqual(get_geo_user_property(self.DOMAIN), GPS_POINT_CASE_PROPERTY)

    def test_custom_config_set(self):
        case_geo_property = "where-art-thou"
        user_geo_property = "right-here"

        config = GeoConfig(
            domain=self.DOMAIN,
            case_location_property_name=case_geo_property,
            user_location_property_name=user_geo_property,
        )
        config.save()
        self.addCleanup(config.delete)

        self.assertEqual(get_geo_case_property(self.DOMAIN), case_geo_property)
        self.assertEqual(get_geo_user_property(self.DOMAIN), user_geo_property)

    def test_invalid_domain_provided(self):
        self.assertEqual(get_geo_case_property(None), GPS_POINT_CASE_PROPERTY)
        self.assertEqual(get_geo_user_property(None), GPS_POINT_CASE_PROPERTY)


@es_test(requires=[case_search_adapter], setup_class=True)
class TestSetGPSProperty(TestCase):
    DOMAIN = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.DOMAIN)

        case_type = 'foobar'

        cls.case_obj = create_case(
            cls.DOMAIN,
            case_id=uuid4().hex,
            case_type=case_type,
            name='CaseA',
            save=True,
        )
        case_search_adapter.bulk_index([cls.case_obj], refresh=True)

        cls.user = CommCareUser.create(
            cls.DOMAIN, 'UserA', '1234', None, None
        )

    @classmethod
    def tearDownClass(cls):
        CommCareCase.objects.hard_delete_cases(cls.DOMAIN, [
            cls.case_obj.case_id,
        ])
        cls.user.delete(cls.DOMAIN, None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_set_case_gps_property(self):
        submit_data = {
            'id': self.case_obj.case_id,
            'name': self.case_obj.name,
            'lat': '1.23',
            'lon': '4.56',
        }
        set_case_gps_property(self.DOMAIN, submit_data)
        case_obj = CommCareCase.objects.get_case(self.case_obj.case_id, self.DOMAIN)
        self.assertEqual(case_obj.case_json[GPS_POINT_CASE_PROPERTY], '1.23 4.56 0.0 0.0')

    def test_create_case_with_gps_property(self):
        case_type = 'gps-case'
        submit_data = {
            'name': 'CaseB',
            'lat': '1.23',
            'lon': '4.56',
            'case_type': case_type,
            'owner_id': self.user.user_id,
        }
        create_case_with_gps_property(self.DOMAIN, submit_data)
        case_list = CommCareCase.objects.get_case_ids_in_domain(self.DOMAIN, case_type)
        self.assertEqual(len(case_list), 1)
        case_obj = CommCareCase.objects.get_case(case_list[0], self.DOMAIN)
        self.assertEqual(case_obj.case_json[GPS_POINT_CASE_PROPERTY], '1.23 4.56 0.0 0.0')

    def test_set_user_gps_property(self):
        submit_data = {
            'id': self.user.user_id,
            'name': self.user.username,
            'lat': '1.23',
            'lon': '4.56',
        }
        set_user_gps_property(self.DOMAIN, submit_data)
        user = CommCareUser.get_by_user_id(self.user.user_id, self.DOMAIN)
        self.assertEqual(user.get_user_data(self.DOMAIN)[GPS_POINT_CASE_PROPERTY], '1.23 4.56 0.0 0.0')
