from uuid import uuid4

from django.test import TestCase

from casexml.apps.case.cleanup import claim_case, get_first_claims
from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq.apps.case_search.models import CLAIM_CASE_TYPE
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.ota.utils import get_restore_user
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase

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
        self.user = CommCareUser.create(DOMAIN, USERNAME, PASSWORD, None, None)
        self.restore_user = get_restore_user(DOMAIN, self.user, None)
        self.host_case_id = uuid4().hex
        self.host_case_name = 'Dmitri Bashkirov'
        self.host_case_type = 'person'
        self.create_case()

    def tearDown(self):
        self.user.delete(self.domain.name, deleted_by=None)
        self.domain.delete()
        super(CaseClaimTests, self).tearDown()

    def create_case(self):
        case_block = CaseBlock(
            create=True,
            case_id=self.host_case_id,
            case_name=self.host_case_name,
            case_type=self.host_case_type,
            owner_id="not the user",
        ).as_text()
        submit_case_blocks(case_block, domain=DOMAIN)

    def assert_claim(self, claim=None, claim_id=None):
        if claim is None:
            claim_ids = CommCareCase.objects.get_case_ids_in_domain(DOMAIN, CLAIM_CASE_TYPE)
            self.assertEqual(len(claim_ids), 1)
            claim = CommCareCase.objects.get_case(claim_ids[0], DOMAIN)
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

    def test_claim_case(self):
        """
        claim_case should create an extension case
        """
        claim_id = claim_case(DOMAIN, self.restore_user, self.host_case_id,
                              host_type=self.host_case_type, host_name=self.host_case_name)
        self.assert_claim(claim_id=claim_id)

    def test_claim_case_id_only(self):
        """
        claim_case should look up host case details if only ID is passed
        """
        claim_id = claim_case(DOMAIN, self.restore_user, self.host_case_id)
        self.assert_claim(claim_id=claim_id)

    def test_first_claim_one(self):
        """
        get_first_claim should return one claim
        """
        claim_case(DOMAIN, self.restore_user, self.host_case_id,
                host_type=self.host_case_type, host_name=self.host_case_name)
        claim = get_first_claims(DOMAIN, self.user.user_id, [self.host_case_id])
        self.assertEqual(len(claim), 1)

    def test_first_claim_none(self):
        """
        get_first_claim should return None if not found
        """
        claim = get_first_claims(DOMAIN, self.user.user_id, [self.host_case_id])
        self.assertEqual(len(claim), 0)

    def test_closed_claim(self):
        """
        get_first_claim should return None if claim case is closed
        """
        claim_id = claim_case(DOMAIN, self.restore_user, self.host_case_id,
                              host_type=self.host_case_type, host_name=self.host_case_name)
        self._close_case(claim_id)
        first_claim = get_first_claims(DOMAIN, self.user.user_id, [self.host_case_id])
        self.assertEqual(len(first_claim), 0)

    def test_get_first_claims_index_not_host(self):
        # create a claim case with the incorrect index identifier
        # method still find the case and recognise it as a claim
        case_block = CaseBlock(
            create=True,
            case_id=uuid4().hex,
            case_name="claim",
            case_type=CLAIM_CASE_TYPE,
            owner_id=self.user.user_id,
            index={
                "not_host": IndexAttrs(
                    case_type=self.host_case_type,
                    case_id=self.host_case_id,
                    relationship=CASE_INDEX_EXTENSION,
                )
            }
        ).as_text()
        submit_case_blocks(case_block, domain=DOMAIN)
        first_claim = get_first_claims(DOMAIN, self.user.user_id, [self.host_case_id])
        self.assertEqual(first_claim, {self.host_case_id})

    def test_claim_index_deleted(self):
        """
        get_first_claim should return None if claim case is closed
        """
        claim_id = claim_case(DOMAIN, self.restore_user, self.host_case_id,
                              host_type=self.host_case_type, host_name=self.host_case_name)

        # delete the case index
        case_block = CaseBlock(
            create=False,
            case_id=claim_id,
            index={"host": (self.host_case_type, "")}
        ).as_text()
        submit_case_blocks(case_block, domain=DOMAIN)

        first_claim = get_first_claims(DOMAIN, self.user.user_id, [self.host_case_id])
        self.assertEqual(len(first_claim), 0)

    def test_claim_case_other_domain(self):
        malicious_domain = 'malicious_domain'
        domain_obj = create_domain(malicious_domain)
        self.addCleanup(domain_obj.delete)
        claim_id = claim_case(malicious_domain, self.restore_user, self.host_case_id,
                              host_type=self.host_case_type, host_name=self.host_case_name)
        with self.assertRaises(CaseNotFound):
            CommCareCase.objects.get_case(claim_id, malicious_domain)

    def _close_case(self, case_id):
        case_block = CaseBlock(
            create=False,
            case_id=case_id,
            close=True
        ).as_text()
        submit_case_blocks(case_block, domain=DOMAIN)
