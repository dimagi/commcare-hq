import uuid

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    case_search_es_teardown,
    es_test,
    populate_case_search_index,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils
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
class TestCaseAPIBulkGet(TestCase):
    domain = 'test-bulk-get-cases'
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

        xform, [case] = submit_case_blocks(
            cls._make_case_block('Vera Menchik', external_id='vera').as_text(), domain='other-domain'
        )
        populate_case_search_index([case])
        cls.other_domain_case_id = case.case_id

    def setUp(self):
        self.client.login(username='netflix', password='password')

    @classmethod
    def tearDownClass(cls):
        cls.web_user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        FormProcessorTestUtils.delete_all_cases(cls.domain)
        FormProcessorTestUtils.delete_all_xforms(cls.domain)
        case_search_es_teardown()
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
        self._call_api_check_results(case_ids)

    def test_bulk_get_domain_filter(self):
        case_ids = self.case_ids[0:2] + [self.other_domain_case_id]
        result = self._call_api_check_results(case_ids)
        self.assertEqual(result['matching_records'], 2)
        self.assertEqual(result['missing_records'], 1)
        self.assertEqual(result['cases'][2]['error'], 'not found')

    def test_bulk_get_not_found(self):
        case_ids = ['missing'] + self.case_ids[0:2]
        result = self._call_api_check_results(case_ids)
        self.assertEqual(result['matching_records'], 2)
        self.assertEqual(result['missing_records'], 1)
        self.assertEqual(result['cases'][0]['error'], 'not found')

    def _call_api_check_results(self, case_ids):
        res = self.client.get(reverse('case_api', args=(self.domain, ','.join(case_ids))))
        self.assertEqual(res.status_code, 200)
        result = res.json()
        result_case_ids = [case['case_id'] for case in result['cases']]
        self.assertEqual(result_case_ids, case_ids)
        return result
