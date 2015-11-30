from django.test import TestCase
from casexml.apps.case.mock import CaseFactory
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests import FormProcessorTestUtils

DOMAIN = 'ledger-tests'


class LedgerTests(TestCase):

    @classmethod
    def setUpClass(cls):
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)
        cls.product = make_product(DOMAIN, 'A Product', 'prodcode')

    def setUp(self):
        self.interface = FormProcessorInterface()
        self.factory = CaseFactory(domain=DOMAIN)
        self.case = self.factory.create_case()

    def _submit_ledgers(self, ledger_block):
        return submit_case_blocks(
            ledger_block.format(case_id=self.case.case_id, product_id=self.product._id), DOMAIN
        )

    def test_balance_submission(self):
        BALANCE_BLOCK = """
        <balance xmlns="http://commcarehq.org/ledger/v1" entity-id="{case_id}" date="2000-01-01" section-id="stock">
            <entry id="{product_id}" quantity="100" />
        </balance>
        """
        self._submit_ledgers(BALANCE_BLOCK)

