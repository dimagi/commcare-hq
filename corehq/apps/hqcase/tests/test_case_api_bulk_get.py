import uuid
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
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
from corehq.apps.data_dictionary.models import CaseType


@es_test(requires=[case_search_adapter], setup_class=True)
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
        cls.deprecated_case_type = 'person'
        case_blocks = [
            cls._make_case_block('Vera Menchik', external_id='vera'),
            cls._make_case_block('Nona Gaprindashvili', external_id='nona'),
            cls._make_case_block('Maia Chiburdanidze', case_type=cls.deprecated_case_type, external_id='maia'),
        ]
        case_search_es_setup(cls.domain, case_blocks)
        cls.case_ids = [b.case_id for b in case_blocks]

        xform, [case] = submit_case_blocks(
            cls._make_case_block('Vera Menchik', external_id='vera').as_text(), domain='other-domain'
        )
        populate_case_search_index([case])
        cls.other_domain_case_id = case.case_id

        cls.case_type_obj = CaseType(domain=cls.domain, name=cls.deprecated_case_type)
        cls.case_type_obj.save()

    def setUp(self):
        self.client.login(username='netflix', password='password')

    @classmethod
    def tearDownClass(cls):
        cls.web_user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        FormProcessorTestUtils.delete_all_cases(cls.domain)
        FormProcessorTestUtils.delete_all_xforms(cls.domain)
        cls.case_type_obj.delete()
        super().tearDownClass()

    @classmethod
    def _make_case_block(cls, name, case_type='player', external_id=None):
        return CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type=case_type,
            case_name=name,
            external_id=external_id,
        )

    def test_get_single_case(self):
        res = self.client.get(reverse('case_api', args=(self.domain, self.case_ids[0])))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['case_id'], self.case_ids[0])

    def test_get_single_case_not_found(self):
        res = self.client.get(reverse('case_api', args=(self.domain, 'fake_id')))
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()['error'], "Case 'fake_id' not found")

    def test_get_single_case_on_other_domain(self):
        res = self.client.get(reverse('case_api', args=(self.domain, self.other_domain_case_id)))
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()['error'], f"Case '{self.other_domain_case_id}' not found")

    def test_bulk_get(self):
        case_ids = self.case_ids[0:2]
        self._call_get_api_check_results(case_ids, matching=2, missing=0)

    def test_bulk_get_domain_filter(self):
        case_ids = self.case_ids[0:2] + [self.other_domain_case_id]
        result = self._call_get_api_check_results(case_ids, matching=2, missing=1)
        self.assertEqual(result['cases'][2]['error'], 'not found')

    def test_bulk_get_not_found(self):
        case_ids = ['missing1', self.case_ids[1], 'missing2']
        result = self._call_get_api_check_results(case_ids, matching=1, missing=2)
        self.assertEqual(result['cases'][0]['error'], 'not found')
        self.assertEqual(result['cases'][2]['error'], 'not found')

    def test_bulk_get_duplicate(self):
        """Duplicate case IDs in the request results in duplicates in the response"""
        case_ids = [self.case_ids[0], 'missing', self.case_ids[2], 'missing', self.case_ids[1], self.case_ids[2]]
        self._call_get_api_check_results(case_ids, matching=4, missing=2)

    def test_bulk_post(self):
        case_ids = self.case_ids[0:2]
        self._call_post_api_check_results(case_ids, matching=2, missing=0)

    def test_bulk_post_missing(self):
        self._call_post_api_check_results(
            case_ids=['missing1', self.case_ids[1], 'missing2'],
            matching=1, missing=2
        )

    def test_bulk_post_duplicates(self):
        """Duplicate case IDs in the request results in duplicates in the response"""
        case_ids = [self.case_ids[0], 'missing', self.case_ids[0], 'missing', 'missing']
        self._call_post_api_check_results(case_ids, matching=2, missing=3)

    def test_bulk_post_over_limit(self):
        with patch('corehq.apps.hqcase.api.get_bulk.MAX_PAGE_SIZE', 3):
            self._call_post(['1', '2', '3', '4'], expected_status=400)

    def test_bulk_post_external_ids(self):
        self._call_post_api_check_results(external_ids=['vera', 'nona'], matching=2, missing=0)

    def test_bulk_post_external_ids_missing(self):
        self._call_post_api_check_results(external_ids=['missing', 'vera', 'nona'], matching=2, missing=1)

    def test_bulk_post_external_ids_duplicates(self):
        """Duplicate case IDs in the request results in duplicates in the response"""
        ids = ['vera', 'missing', 'nona', 'vera', 'missing']
        self._call_post_api_check_results(external_ids=ids, matching=3, missing=2)

    def test_bulk_post_case_ids_and_external_ids(self):
        self._call_post_api_check_results(
            case_ids=self.case_ids[0:2],
            external_ids=['vera', 'nona'],
            matching=4, missing=0
        )

    def test_bulk_post_case_ids_and_external_ids_duplicates(self):
        self._call_post_api_check_results(
            case_ids=[self.case_ids[0], self.case_ids[0]],
            external_ids=['vera', 'vera'],
            matching=4, missing=0
        )

    def test_bulk_post_case_ids_and_external_ids_missing(self):
        self._call_post_api_check_results(
            case_ids=['missing_case_id'] + self.case_ids[0:2],
            external_ids=['vera', 'missing_external_id', 'nona'],
            matching=4, missing=2
        )

    def _call_get_api_check_results(self, case_ids, matching=None, missing=None):
        res = self.client.get(reverse('case_api', args=(self.domain, ','.join(case_ids))))
        self.assertEqual(res.status_code, 200)
        result = res.json()
        result_case_ids = [case['case_id'] for case in result['cases']]
        self.assertEqual(result_case_ids, case_ids)
        self._check_matching_missing(result, matching, missing)
        return result

    def _call_post_api_check_results(self, case_ids=None, external_ids=None, matching=None, missing=None):
        res = self._call_post(case_ids, external_ids)
        result = res.json()
        cases = result['cases']

        self._check_matching_missing(result, matching, missing)

        total_expected = len(case_ids or []) + len(external_ids or [])
        self.assertEqual(len(cases), total_expected)

        # check for results as well as result order
        if case_ids:
            # case_id results are always at the front
            result_case_ids = [case.get('case_id') for case in cases]
            self.assertEqual(case_ids, result_case_ids[:len(case_ids)])

        if external_ids:
            # external_id results are always at the end so reverse the lists and compare
            external_ids = list(reversed(external_ids))
            result_external_ids = list(reversed([
                case.get('external_id') for case in cases
            ]))
            self.assertEqual(external_ids, result_external_ids[:len(external_ids)])

        return result

    def _call_post(self, case_ids=None, external_ids=None, expected_status=200):
        data = {}
        if case_ids is not None:
            data['case_ids'] = case_ids
        if external_ids is not None:
            data['external_ids'] = external_ids
        url = reverse('case_api_bulk_fetch', args=(self.domain,))
        res = self.client.post(url, data=data, content_type="application/json")
        self.assertEqual(res.status_code, expected_status, res.json())
        return res

    def _check_matching_missing(self, result, matching=None, missing=None):
        if matching is not None:
            self.assertEqual(result['matching_records'], matching)

        if missing is not None:
            self.assertEqual(result['missing_records'], missing)
