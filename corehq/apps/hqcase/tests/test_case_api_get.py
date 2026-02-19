import uuid

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
from corehq.apps.hqcase.api.core import serialize_case
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.util.test_utils import (
    disable_quickcache,
    flag_enabled,
    privilege_enabled,
)


@es_test(requires=[case_search_adapter], setup_class=True)
@disable_quickcache
@privilege_enabled(privileges.API_ACCESS)
@flag_enabled('API_THROTTLE_WHITELIST')
class TestCaseAPIGet(TestCase):
    domain = 'test-get-cases'
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
        res = self.client.get(reverse('case_api_detail', args=(self.domain, self.case_ids[0])))
        assert res.status_code == 200
        assert res.json()['case_id'] == self.case_ids[0]

    def test_get_single_case_by_external_id(self):
        case_id = '11111111-1111-4111-8111-111111111111'
        external_id = 'ext-get-case'
        case_block = CaseBlock(
            case_id=case_id,
            case_type='player',
            case_name='Irina Levitina',
            external_id=external_id,
            owner_id=self.web_user.get_id,
            create=True,
        )
        _, [case] = submit_case_blocks(case_block.as_text(), domain=self.domain)
        populate_case_search_index([case])
        expected = serialize_case(case)

        base_url = reverse('case_api', args=(self.domain,))
        if not base_url.endswith('/'):
            base_url += '/'
        url = f"{base_url}ext/{external_id}/"
        res = self.client.get(url)

        assert res.status_code == 200
        response_data = res.json()
        response_data.pop('indexed_on')  # milliseconds won't match
        expected.pop('indexed_on')
        assert response_data == expected

    def test_get_case_by_external_id_not_found(self):
        base_url = reverse('case_api', args=(self.domain,))
        if not base_url.endswith('/'):
            base_url += '/'
        url = f"{base_url}ext/missing-external-id/"
        res = self.client.get(url)

        assert res.status_code == 404
        assert res.json()['error'] == "Case 'missing-external-id' not found"

    def test_get_single_case_not_found(self):
        res = self.client.get(reverse('case_api_detail', args=(self.domain, 'fake_id')))
        assert res.status_code == 404
        assert res.json()['error'] == "Case 'fake_id' not found"

    def test_get_single_case_on_other_domain(self):
        res = self.client.get(reverse('case_api_detail', args=(self.domain, self.other_domain_case_id)))
        assert res.status_code == 404
        assert res.json()['error'] == f"Case '{self.other_domain_case_id}' not found"

    def test_get_case_by_external_id_with_duplicates(self):
        external_id = 'duplicate-external-id-get'
        case_block_1 = CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='player',
            case_name='Player 1',
            external_id=external_id,
            owner_id=self.web_user.get_id,
            create=True,
        ).as_text()
        case_block_2 = CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='player',
            case_name='Player 2',
            external_id=external_id,
            owner_id=self.web_user.get_id,
            create=True,
        ).as_text()
        _, (case1, case2) = submit_case_blocks(
            [case_block_1, case_block_2],
            domain=self.domain,
        )
        populate_case_search_index([case1, case2])  # needed for permission checks

        url = reverse('case_api_detail_ext', args=(self.domain, external_id))
        res = self.client.get(url)

        assert res.status_code == 400
        error_response = res.json()
        assert 'Multiple cases found' in error_response['error']
        assert external_id in error_response['error']
        assert case1.case_id in error_response['error']
        assert case2.case_id in error_response['error']
