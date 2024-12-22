from uuid import uuid4

from django.test import TestCase, SimpleTestCase

from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.geospatial.const import ASSIGNED_VIA_DISBURSEMENT_CASE_PROPERTY, GPS_POINT_CASE_PROPERTY
from corehq.apps.geospatial.models import GeoConfig
from corehq.apps.geospatial.utils import (
    CaseOwnerUpdate,
    CeleryTaskTracker,
    create_case_with_gps_property,
    get_flag_assigned_cases_config,
    get_geo_case_property,
    get_geo_user_property,
    set_case_gps_property,
    set_user_gps_property,
    update_cases_owner,
    get_celery_task_tracker,
)
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.form_processor.tests.utils import create_case
from corehq.tests.locks import real_redis_client


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


class TestUpdateCasesOwner(TestCase):
    domain = 'test-domain'

    def setUp(self):
        super().setUp()
        self.user_a = CommCareUser.create(self.domain, 'User_A', '1234', None, None)
        self.case_1 = create_case(self.domain, case_id=uuid4().hex, save=True, owner_id=self.user_a.user_id)

        self.user_b = CommCareUser.create(self.domain, 'User_B', '1234', None, None)
        self.case_2 = create_case(self.domain, case_id=uuid4().hex, save=True, owner_id=self.user_b.user_id)
        self.related_case_2 = create_case(
            self.domain,
            case_id=uuid4().hex,
            save=True,
            owner_id=self.user_b.user_id
        )
        self._create_parent_index(self.related_case_2, self.case_2.case_id)

        self.cases = [self.case_1, self.case_2, self.related_case_2]

    def tearDown(self):
        self.user_a.delete(self.domain, None)
        self.user_b.delete(self.domain, None)
        CommCareCase.objects.hard_delete_cases(
            self.domain,
            [case.case_id for case in self.cases]
        )
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

    def _assert_for_assigned_cases_flag_absent(self):
        for case in self.cases:
            self.assertIsNone(case.case_json.get(ASSIGNED_VIA_DISBURSEMENT_CASE_PROPERTY))

    def _assert_for_assigned_cases_flag_present(self):
        for case in self.cases:
            self.assertTrue(case.case_json.get(ASSIGNED_VIA_DISBURSEMENT_CASE_PROPERTY))

    def test_update_cases_owner(self):
        case_owner_updates = [
            CaseOwnerUpdate(case_id=self.case_1.case_id, owner_id=self.user_b.user_id),
            CaseOwnerUpdate(
                case_id=self.case_2.case_id,
                owner_id=self.user_a.user_id,
                related_case_ids=[self.related_case_2.case_id]),
        ]

        update_cases_owner(self.domain, CaseOwnerUpdate.to_dict(case_owner_updates))

        self._refresh_cases()
        self.assertEqual(self.case_1.owner_id, self.user_b.user_id)
        self.assertEqual(self.case_2.owner_id, self.user_a.user_id)
        self.assertEqual(self.related_case_2.owner_id, self.user_a.user_id)
        self._assert_for_assigned_cases_flag_absent()

    def test_update_cases_owner_with_flag_assigned_cases(self):
        case_owner_updates = [
            CaseOwnerUpdate(case_id=self.case_1.case_id, owner_id=self.user_b.user_id),
            CaseOwnerUpdate(
                case_id=self.case_2.case_id,
                owner_id=self.user_a.user_id,
                related_case_ids=[self.related_case_2.case_id]),
        ]

        update_cases_owner(self.domain, CaseOwnerUpdate.to_dict(case_owner_updates), flag_assigned_cases=True)

        self._refresh_cases()
        self.assertEqual(self.case_1.owner_id, self.user_b.user_id)
        self.assertEqual(self.case_2.owner_id, self.user_a.user_id)
        self.assertEqual(self.related_case_2.owner_id, self.user_a.user_id)
        self._assert_for_assigned_cases_flag_present()


class TestCeleryTaskTracker(TestCase):
    TASK_KEY = 'test-key'
    PROGRESS_KEY = 'test-key_progress'
    ERROR_SLUG_KEY = 'test-key_error_slug'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with real_redis_client():
            cls.redis_client = get_redis_client()
            cls.celery_task_tracker = CeleryTaskTracker(cls.TASK_KEY)

    def tearDown(self):
        self.redis_client.clear()
        super().tearDown()

    def test_mark_active(self):
        self.celery_task_tracker.mark_requested()
        self.assertTrue(self.redis_client.get(self.TASK_KEY), 'ACTIVE')

    def test_get_active(self):
        self.redis_client.set(self.TASK_KEY, 'ACTIVE')
        self.assertTrue(self.celery_task_tracker.is_active())

    def test_mark_inactive(self):
        self.redis_client.set(self.TASK_KEY, 'ACTIVE')
        self.celery_task_tracker.mark_completed()
        self.assertFalse(self.redis_client.has_key(self.TASK_KEY))

    def test_mark_error(self):
        self.celery_task_tracker.mark_as_error(error_slug='TEST')
        self.assertEqual(self.redis_client.get(self.TASK_KEY), 'ERROR')
        self.assertEqual(self.redis_client.get(self.ERROR_SLUG_KEY), 'TEST')

    def test_get_status(self):
        self.redis_client.set(self.TASK_KEY, 'ERROR')
        self.redis_client.set(self.ERROR_SLUG_KEY, 'TEST')
        expected_output = {
            'status': 'ERROR',
            'progress': 0,
            'error_slug': 'TEST'
        }
        self.assertEqual(self.celery_task_tracker.get_status(), expected_output)

    def test_set_progress(self):
        self.assertTrue(self.celery_task_tracker.update_progress(current=1, total=5))
        self.assertTrue(self.redis_client.has_key(self.PROGRESS_KEY))
        self.assertEqual(self.redis_client.get(self.PROGRESS_KEY), 20)

    def test_get_progress(self):
        self.assertEqual(self.celery_task_tracker.get_progress(), 0)
        self.celery_task_tracker.update_progress(current=1, total=4)
        self.assertEqual(self.celery_task_tracker.get_progress(), 25)

    def test_clear_progress(self):
        self.assertFalse(self.celery_task_tracker.clear_progress())
        self.celery_task_tracker.update_progress(current=1, total=2)
        self.assertTrue(self.celery_task_tracker.clear_progress())
        self.assertFalse(self.redis_client.has_key(self.PROGRESS_KEY))

    def test_invalid_progress(self):
        self.celery_task_tracker.update_progress(current=3, total=0)
        self.assertEqual(self.celery_task_tracker.get_progress(), 0)


class TestGetCeleryTaskTracker(SimpleTestCase):
    domain = 'foobar'
    base_key = 'test_me'

    def test_get_celery_task_tracker(self):
        celery_task_tracker = get_celery_task_tracker(self.domain, self.base_key)
        self.assertEqual(
            celery_task_tracker.task_key,
            'test_me_foobar'
        )
        self.assertEqual(
            celery_task_tracker.progress_key,
            'test_me_foobar_progress'
        )


class TestGetFlagAssignedCasesConfig(TestCase):

    DOMAIN = "test-domain"

    def test_flag_not_set(self):
        self.assertFalse(get_flag_assigned_cases_config(self.DOMAIN))

    def test_flag_set(self):
        config = GeoConfig(
            domain=self.DOMAIN,
            flag_assigned_cases=True,
        )
        config.save()
        self.addCleanup(config.delete)

        self.assertTrue(get_flag_assigned_cases_config(self.DOMAIN))

    def test_invalid_domain_provided(self):
        self.assertFalse(get_flag_assigned_cases_config(None))
