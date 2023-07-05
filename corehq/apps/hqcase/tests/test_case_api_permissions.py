import uuid
from contextlib import contextmanager

from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock

from corehq import privileges
from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import case_search_es_setup, es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.es.cases import case_adapter
from corehq.apps.hqcase.api.get_list import get_list
from corehq.apps.locations.tests.util import setup_locations_and_types
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.util.es.testing import sync_users_to_es
from corehq.util.test_utils import (
    disable_quickcache,
    flag_enabled,
    privilege_enabled,
)


@es_test(requires=[
    case_search_adapter,
    form_adapter,
    user_adapter,
    case_adapter,
], setup_class=True)
@disable_quickcache
@privilege_enabled(privileges.API_ACCESS)
@flag_enabled('CASE_API_V0_6')
@flag_enabled('API_THROTTLE_WHITELIST')
class TestCaseAPIPermissions(TestCase):
    domain = 'test-case-api-permissions'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = bootstrap_domain(cls.domain)
        CaseSearchConfig.objects.create(pk=cls.domain, enabled=True)
        location_types, locations = setup_locations_and_types(
            cls.domain,
            location_types=['country'],
            stock_tracking_types=[],
            locations=[('USA', []), ('RSA', [])],
        )

        cls.user_location = locations['RSA']
        cls.restricted_location = locations['USA']

        names_locations = [
            ('Joe', locations['USA']),
            ('Cyril', locations['RSA']),
        ]
        case_blocks = get_case_blocks(names_locations)
        case_search_es_setup(cls.domain, case_blocks)
        cls.case_ids = [cb.case_id for cb in case_blocks]

        cls.case_mapping = {
            'restricted_case': cls.case_ids[0],
            'user_case': cls.case_ids[1]
        }

        cls.base_permissions = {
            'edit_data': True,
            'access_api': True
        }
        cls.location_restricted_permissions = cls.base_permissions | {
            'access_all_locations': False
        }
        cls.access_all_locations_permissions = cls.base_permissions | {
            'access_all_locations': True
        }

        cls.test_case_property = {
            'foo': 'bar'
        }

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        cls.domain_obj.delete()
        super().tearDownClass()

    def _get_new_case_data(self, is_restricted=False):
        data = {
            'temporary_id': '1',
            'case_name': 'test',
            'case_type': 'case',
            'properties': self.test_case_property
        }
        if is_restricted:
            data['owner_id'] = self.restricted_location.location_id
        else:
            data['owner_id'] = self.user_location.location_id
        return data

    def test_case_api_list_happy_path(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.base_permissions,
            self.client,
        ):
            url = reverse('case_api', args=(self.domain,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            json = response.json()
            self.assertEqual(json['matching_records'], 2)

    def test_case_api_list_location_restricted(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.location_restricted_permissions,
            self.client,
        ):
            url = reverse('case_api', args=(self.domain,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            json = response.json()
            self.assertEqual(json['matching_records'], 1)

    def test_case_api_bulk_fetch_happy_path(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.base_permissions,
            self.client,
        ):
            url = reverse('case_api_bulk_fetch', args=(self.domain,))
            response = self.client.post(
                url,
                {'case_ids': self.case_ids},
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)
            json = response.json()
            self.assertEqual(json['matching_records'], 2)

    def test_case_api_bulk_fetch_requires_access_all_locations(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.location_restricted_permissions,
            self.client,
        ):
            url = reverse('case_api_bulk_fetch', args=(self.domain,))
            response = self.client.post(
                url,
                {'case_ids': self.case_ids},
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 403)

    def test_case_api_get_successful(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.location_restricted_permissions,
            self.client,
        ):
            case_id = self.case_mapping['user_case']
            url = reverse('case_api', args=(self.domain, case_id))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            json = response.json()
            self.assertEqual(json['case_id'], case_id)

    def test_case_api_get_no_permission(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.location_restricted_permissions,
            self.client,
        ):
            case_id = self.case_mapping['restricted_case']
            url = reverse('case_api', args=(self.domain, case_id))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_case_api_get_access_all_locations(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.access_all_locations_permissions,
            self.client,
        ):
            case_id = self.case_mapping['restricted_case']
            url = reverse('case_api', args=(self.domain, case_id))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            json = response.json()
            self.assertEqual(json['case_id'], case_id)

    def test_case_api_update_successful(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.location_restricted_permissions,
            self.client,
        ):
            case_id = self.case_mapping['user_case']
            url = reverse('case_api', args=(self.domain, case_id))
            response = self.client.put(
                url,
                {'properties': self.test_case_property},
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            json = response.json()
            self.assertEqual(json['case']['properties'], self.test_case_property)

    def test_case_api_update_no_permission(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.location_restricted_permissions,
            self.client,
        ):
            case_id = self.case_mapping['restricted_case']
            url = reverse('case_api', args=(self.domain, case_id))
            response = self.client.put(
                url,
                {'properties': self.test_case_property},
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 403)

    def test_case_api_update_access_all_locations(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.access_all_locations_permissions,
            self.client,
        ):
            case_id = self.case_mapping['restricted_case']
            url = reverse('case_api', args=(self.domain, case_id))
            response = self.client.put(
                url,
                {'properties': self.test_case_property},
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            json = response.json()
            self.assertEqual(json['case']['properties'], self.test_case_property)

    def test_case_api_update_new_owner_no_permission(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.location_restricted_permissions,
            self.client,
        ):
            case_update = {
                'case_id': self.case_mapping['user_case'],
                'owner_id': self.restricted_location.location_id,
                'properties': self.test_case_property
            }
            url = reverse('case_api', args=(self.domain,))
            response = self.client.put(url, case_update, content_type='application/json')
            self.assertEqual(response.status_code, 403)

    def test_case_api_create_successful(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.location_restricted_permissions,
            self.client,
        ):
            url = reverse('case_api', args=(self.domain,))
            response = self.client.post(
                url,
                self._get_new_case_data(),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            json = response.json()
            self.assertEqual(json['case']['properties'], self.test_case_property)

    def test_case_api_create_no_permission(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.location_restricted_permissions,
            self.client,
        ):
            url = reverse('case_api', args=(self.domain,))
            response = self.client.post(
                url,
                self._get_new_case_data(is_restricted=True),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 403)

    def test_case_api_create_access_all_locations(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.access_all_locations_permissions,
            self.client,
        ):
            url = reverse('case_api', args=(self.domain,))
            response = self.client.post(
                url,
                self._get_new_case_data(is_restricted=True),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            json = response.json()
            self.assertEqual(json['case']['properties'], self.test_case_property)

    def test_get_list_access_all_locations(self):
        with get_web_user(
            self.domain,
            self.user_location,
            self.access_all_locations_permissions,
            self.client,
        ) as web_user:
            result = get_list(self.domain, web_user, params=QueryDict())
            self.assertEqual(result['matching_records'], 2)
            self.assertEqual(
                {c['case_name'] for c in result['cases']},
                {'Joe', 'Cyril'},
            )

    def test_get_list_location_restricted(self):
        with sync_users_to_es():
            with get_web_user(
                self.domain,
                self.user_location,
                self.location_restricted_permissions,
                self.client,
            ) as web_user:
                result = get_list(self.domain, web_user, params=QueryDict())
                self.assertEqual(result['matching_records'], 1)
                self.assertEqual(result['cases'][0]['case_name'], 'Cyril')


@contextmanager
def get_web_user(domain, location, permissions, client):
    username = 'admin@example.com'
    password = '************'
    role = UserRole.create(
        domain,
        'edit-data',
        permissions=HqPermissions(**permissions),
    )

    web_user = WebUser.create(
        domain,
        username,
        password,
        created_by=None,
        created_via=None,
        role_id=role.get_id,
    )
    web_user.set_location(domain, location)
    manager.index_refresh(user_adapter.index_name)
    client.login(username=username, password=password)
    try:
        yield web_user
    finally:
        web_user.delete(domain, deleted_by=None)
        role.delete()


def get_case_blocks(names_locations):
    return [
        CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='person',
            case_name=name,
            owner_id=location.location_id,
        ) for name, location in names_locations
    ]
