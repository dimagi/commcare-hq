from uuid import uuid4

from django.core.urlresolvers import reverse
from django.test import TestCase, Client

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from corehq.apps.case_search.models import CLAIM_CASE_TYPE
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests import run_with_all_backends

DOMAIN = 'test-domain'
USERNAME = 'testy_mctestface'
PASSWORD = '123'
CASE_NAME = 'Jamie Hand'


class ClaimCaseTests(TestCase):

    @classmethod
    def setUpClass(cls):
        create_domain(DOMAIN)
        cls.user = CommCareUser.create(DOMAIN, USERNAME, PASSWORD)
        cls.case_id = uuid4().hex
        _, [cls.case] = post_case_blocks([CaseBlock(
            create=True,
            case_id=cls.case_id,
            case_type='case',
            case_name=CASE_NAME,
            owner_id='someone_else',
        ).as_xml()], {'domain': DOMAIN})

    # @run_with_all_backends
    def test_claim_case(self):
        """
        A claim case request should create an extension case
        """
        self.assertEqual(len(CaseAccessors(DOMAIN).get_case_ids_in_domain(CLAIM_CASE_TYPE)), 0)

        client = Client()
        client.login(username=USERNAME, password=PASSWORD)
        url = reverse('claim_case', kwargs={'domain': DOMAIN})
        client.post(url, {'case_id': self.case_id})

        claim_ids = CaseAccessors(DOMAIN).get_case_ids_in_domain(CLAIM_CASE_TYPE)
        self.assertEqual(len(claim_ids), 1)
        claim = CaseAccessors(DOMAIN).get_case(claim_ids[0])
        self.assertEqual(claim.owner_id, self.user.get_id)
        self.assertEqual(claim.name, CASE_NAME)

    # @run_with_all_backends
    def test_search_endpoint(self):
        client = Client()
        client.login(username=USERNAME, password=PASSWORD)
        url = reverse('sync_search', kwargs={'domain': DOMAIN})
        response = client.get(url, {'name': 'Jamie Hand', 'case_type': 'case'})
        self.assertEqual(response.status_code, 200)
        # TODO: self.assertEqual(response.content, known_value)
