import uuid
from contextlib import contextmanager

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock

from corehq import privileges
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    case_search_es_teardown,
    es_test,
)
from corehq.apps.hqcase.api.get_list import get_list
from corehq.apps.locations.tests.util import setup_locations_and_types
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.elastic import get_es_new
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.util.elastic import ensure_index_deleted
from corehq.util.es.testing import sync_users_to_es
from corehq.util.test_utils import (
    disable_quickcache,
    flag_enabled,
    privilege_enabled,
)


@es_test
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
        location_types, locations = setup_locations_and_types(
            cls.domain,
            location_types=['country'],
            stock_tracking_types=[],
            locations= [('USA', []), ('RSA', [])],
        )

        cls.user_location = locations['RSA']

        names_locations = [
            ('Joe', locations['USA']),
            ('Cyril', locations['RSA']),
        ]
        case_blocks = get_case_blocks(names_locations)
        case_search_es_setup(cls.domain, case_blocks)
        cls.case_ids = [cb.case_id for cb in case_blocks]

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        case_search_es_teardown()
        super().tearDownClass()

    def test_case_api_list_happy_path(self):
        permissions = {
            'edit_data': True,
            'access_api': True,
        }
        with get_web_user(
            self.domain,
            self.user_location,
            permissions,
            self.client,
        ):
            url = reverse('case_api', args=(self.domain,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_case_api_list_requires_access_all_locations(self):
        permissions = {
            'edit_data': True,
            'access_api': True,
            'access_all_locations': False,
        }
        with get_web_user(
            self.domain,
            self.user_location,
            permissions,
            self.client,
        ):
            url = reverse('case_api', args=(self.domain,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_case_api_bulk_fetch_happy_path(self):
        permissions = {
            'edit_data': True,
            'access_api': True,
        }
        with get_web_user(
            self.domain,
            self.user_location,
            permissions,
            self.client,
        ):
            url = reverse('case_api_bulk_fetch', args=(self.domain,))
            response = self.client.post(
                url,
                {'case_ids': self.case_ids},
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)

    def test_case_api_bulk_fetch_requires_access_all_locations(self):
        permissions = {
            'edit_data': True,
            'access_api': True,
            'access_all_locations': False,
        }
        with get_web_user(
            self.domain,
            self.user_location,
            permissions,
            self.client,
        ):
            url = reverse('case_api_bulk_fetch', args=(self.domain,))
            response = self.client.post(
                url,
                {'case_ids': self.case_ids},
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 403)

    def test_get_list_access_all_locations(self):
        permissions = {
            'edit_data': True,
            'access_api': True,
            'access_all_locations': True,
        }
        with get_web_user(
            self.domain,
            self.user_location,
            permissions,
            self.client,
        ) as web_user:

            result = get_list(self.domain, web_user, params={})
            self.assertEqual(result['matching_records'], 2)
            self.assertEqual(
                {c['case_name'] for c in result['cases']},
                {'Joe', 'Cyril'},
            )

    def test_get_list_location_restricted(self):
        permissions = {
            'edit_data': True,
            'access_api': True,
            'access_all_locations': False,
        }

        with sync_users_to_es():
            with get_web_user(
                self.domain,
                self.user_location,
                permissions,
                self.client,
            ) as web_user:
                get_es_new().indices.refresh(USER_INDEX)

                result = get_list(self.domain, web_user, params={})
                self.assertEqual(result['matching_records'], 1)
                self.assertEqual(result['cases'][0]['case_name'], 'Cyril')

                ensure_index_deleted(USER_INDEX)


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
