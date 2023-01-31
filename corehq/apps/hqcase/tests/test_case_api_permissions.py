import uuid
from contextlib import contextmanager

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    case_search_es_teardown,
    es_test,
)
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
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
        cls.domain_obj = create_domain(cls.domain)

        case_blocks = get_case_blocks()
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
        with get_web_user(self.domain, self.client, permissions):
            url = reverse('case_api', args=(self.domain,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_case_api_list_requires_access_all_locations(self):
        permissions = {
            'edit_data': True,
            'access_api': True,
            'access_all_locations': False,
        }
        with get_web_user(self.domain, self.client, permissions):
            url = reverse('case_api', args=(self.domain,))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)

    def test_case_api_bulk_fetch_happy_path(self):
        permissions = {
            'edit_data': True,
            'access_api': True,
        }
        with get_web_user(self.domain, self.client, permissions):
            response = self.client.post(
                reverse('case_api_bulk_fetch', args=(self.domain,)),
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
        with get_web_user(self.domain, self.client, permissions):
            response = self.client.post(
                reverse('case_api_bulk_fetch', args=(self.domain,)),
                {'case_ids': self.case_ids},
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 403)


@contextmanager
def get_web_user(domain, client, permissions):
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
    client.login(username=username, password=password)
    try:
        yield web_user
    finally:
        web_user.delete(domain, deleted_by=None)
        role.delete()


def get_case_blocks():
    return [
        CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='person',
            case_name=name,
        ) for name in ('joe', 'cyril')
    ]
