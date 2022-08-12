import uuid

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock
from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test, case_search_es_setup, case_search_es_teardown
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.util.test_utils import disable_quickcache, flag_enabled, privilege_enabled


@es_test
@disable_quickcache
@privilege_enabled(privileges.API_ACCESS)
@flag_enabled('CASE_API_V0_6')
@flag_enabled('API_THROTTLE_WHITELIST')
class TestCaseAPIBulkGet(TestCase):
    domain = 'test-update-cases'
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        role = UserRole.create(
            cls.domain, 'edit-data', permissions=HqPermissions(edit_data=True, access_api=True)
        )
        cls.web_user = WebUser.create(cls.domain, 'netflix', 'password', None, None, role_id=role.get_id)
        case_blocks = [
            cls._make_case_block('Vera Menchik', external_id='vera'),
            cls._make_case_block('Nona Gaprindashvili', external_id='nona'),
            cls._make_case_block('Maia Chiburdanidze', external_id='mia'),
        ]
        case_search_es_setup(cls.domain, case_blocks)
        cls.case_ids = [b.case_id for b in case_blocks]

    def setUp(self):
        self.client.login(username='netflix', password='password')

    def tearDown(self):
        case_search_es_teardown()

    @classmethod
    def tearDownClass(cls):
        cls.web_user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    @classmethod
    def _make_case_block(cls, name, external_id=None):
        return CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='player',
            case_name=name,
            external_id=external_id,
        )

    def test_bulk_get(self):
        case_ids = self.case_ids[0:2]
        res = self.client.get(reverse('case_api', args=(self.domain, ','.join(case_ids))))
        self.assertEqual(res.status_code, 200)
        result_case_ids = [case['case_id'] for case in res.json()['cases']]
        self.assertEqual(result_case_ids, case_ids)
