from __future__ import absolute_import
from __future__ import unicode_literals
from uuid import uuid4
from django.test import TestCase
from casexml.apps.case.cleanup import claim_case, get_first_claim
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from corehq.apps.case_search.models import CLAIM_CASE_TYPE
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends

DOMAIN = 'test_domain'
USERNAME = 'lina.stern@ras.ru'
PASSWORD = 'hemato-encephalic'
# https://en.wikipedia.org/wiki/Lina_Stern


def index_to_dict(instance):
    keys = ('identifier', 'referenced_type', 'referenced_id', 'relationship')
    return {k: str(getattr(instance, k)) for k in keys}


class CaseClaimTests(TestCase):

    def setUp(self):
        super(CaseClaimTests, self).setUp()
        self.domain = create_domain(DOMAIN)
        self.user = CommCareUser.create(DOMAIN, USERNAME, PASSWORD)
        self.host_case_id = uuid4().hex
        self.host_case_name = 'Dmitri Bashkirov'
        self.host_case_type = 'person'
        self.create_case()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()
        super(CaseClaimTests, self).tearDown()

    def create_case(self):
        case_block = CaseBlock(
            create=True,
            case_id=self.host_case_id,
            case_name=self.host_case_name,
            case_type=self.host_case_type,
            owner_id='in_soviet_russia_the_case_owns_you',
        ).as_xml()
        post_case_blocks([case_block], {'domain': DOMAIN})

    def assert_claim(self, claim=None, claim_id=None):
        if claim is None:
            claim_ids = CaseAccessors(DOMAIN).get_case_ids_in_domain(CLAIM_CASE_TYPE)
            self.assertEqual(len(claim_ids), 1)
            claim = CaseAccessors(DOMAIN).get_case(claim_ids[0])
        if claim_id:
            self.assertEqual(claim.case_id, claim_id)
        self.assertEqual(claim.name, self.host_case_name)
        self.assertEqual(claim.owner_id, self.user.user_id)
        self.assertEqual([index_to_dict(i) for i in claim.indices], [{
            'identifier': 'host',
            'referenced_type': 'person',
            'referenced_id': self.host_case_id,
            'relationship': 'extension',
        }])

    @run_with_all_backends
    def test_claim_case(self):
        """
        claim_case should create an extension case
        """
        claim_id = claim_case(DOMAIN, self.user.user_id, self.host_case_id,
                              host_type=self.host_case_type, host_name=self.host_case_name)
        self.assert_claim(claim_id=claim_id)

    @run_with_all_backends
    def test_claim_case_id_only(self):
        """
        claim_case should look up host case details if only ID is passed
        """
        claim_id = claim_case(DOMAIN, self.user.user_id, self.host_case_id)
        self.assert_claim(claim_id=claim_id)

    @run_with_all_backends
    def test_first_claim_one(self):
        """
        get_first_claim should return one claim
        """
        claim_id = claim_case(DOMAIN, self.user.user_id, self.host_case_id,
                              host_type=self.host_case_type, host_name=self.host_case_name)
        claim = get_first_claim(DOMAIN, self.user.user_id, self.host_case_id)
        self.assert_claim(claim, claim_id)

    @run_with_all_backends
    def test_first_claim_none(self):
        """
        get_first_claim should return None if not found
        """
        claim = get_first_claim(DOMAIN, self.user.user_id, self.host_case_id)
        self.assertIsNone(claim)

    @run_with_all_backends
    def test_closed_claim(self):
        """
        get_first_claim should return None if claim case is closed
        """
        claim_id = claim_case(DOMAIN, self.user.user_id, self.host_case_id,
                              host_type=self.host_case_type, host_name=self.host_case_name)
        self._close_case(claim_id)
        first_claim = get_first_claim(DOMAIN, self.user.user_id, self.host_case_id)
        self.assertIsNone(first_claim)

    def _close_case(self, case_id):
        case_block = CaseBlock(
            create=False,
            case_id=case_id,
            close=True
        ).as_xml()
        post_case_blocks([case_block], {'domain': DOMAIN})
