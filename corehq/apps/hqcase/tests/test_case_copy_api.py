import uuid
import json

from django.test import TestCase
from django.urls import reverse
from django_prbac.exceptions import PermissionDenied

from casexml.apps.case.mock import CaseBlock

from corehq.form_processor.models.cases import CommCareCase
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
from corehq.util.test_utils import privilege_enabled, flag_enabled
from corehq import privileges


@es_test(requires=[case_search_adapter], setup_class=True)
class TestCaseCopyAPI(TestCase):
    domain = 'test-domain'
    url_name = 'copy_cases'

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
            cls._make_case_block('Maia Chiburdanidze', external_id='maia'),
        ]
        case_search_es_setup(cls.domain, case_blocks)
        cls.case_ids = [b.case_id for b in case_blocks]

        xform, [case] = submit_case_blocks(
            cls._make_case_block('Vera Menchik', external_id='vera').as_text(), domain='other-domain'
        )
        populate_case_search_index([case])

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
    def _make_case_block(cls, name, external_id=None):
        return CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='player',
            case_name=name,
            external_id=external_id,
        )

    @flag_enabled('COPY_CASES')
    def test_missing_user_permissions(self):
        WebUser.create(self.domain, 'invalid', 'password', None, None)
        self.client.login(username='invalid', password='password')
        res = self.make_post({})
        self.assertEqual(res.status_code, 403)

    @flag_enabled('COPY_CASES')
    def test_missing_domain_permissions(self):
        with self.assertRaises(PermissionDenied):
            self.make_post({})

    @flag_enabled('COPY_CASES')
    @privilege_enabled(privileges.CASE_COPY)
    def test_missing_case_ids(self):
        res = self.make_post({'case_ids': []})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(json.loads(res.content)['error'], "Missing case ids")

    @flag_enabled('COPY_CASES')
    @privilege_enabled(privileges.CASE_COPY)
    def test_missing_owner_id(self):
        res = self.make_post({'case_ids': self.case_ids, 'owner_id': ''})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(json.loads(res.content)['error'], "Missing new owner id")

    @flag_enabled('COPY_CASES')
    @privilege_enabled(privileges.CASE_COPY)
    def test_case_is_copied_to_new_owner(self):
        new_owner_id = 'new_owner_id'

        res = self.make_post({'case_ids': self.case_ids, 'owner_id': new_owner_id})
        self.assertEqual(json.loads(res.content)['copied_cases'], len(self.case_ids))

        copied_case_ids = CommCareCase.objects.get_case_ids_in_domain_by_owners(self.domain, [new_owner_id])
        self.assertEqual(len(copied_case_ids), len(self.case_ids))
        self.assertTrue(sorted(copied_case_ids) != sorted(self.case_ids))

    def make_post(self, data):
        return self.client.generic('POST', self.url, content_type='application/json', data=json.dumps(data))

    @property
    def url(self):
        return reverse(self.url_name, args=(self.domain,))
