from django.test import TestCase
from casexml.apps.case.mock import CaseFactory
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests import FormProcessorTestUtils, run_with_all_backends

DOMAIN = 'ledger-tests'

BALANCE_BLOCK = """
<balance xmlns="http://commcarehq.org/ledger/v1" entity-id="{case_id}" date="2000-01-01" section-id="stock">
    <entry id="{product_id}" quantity="{quantity}" />
</balance>
"""

TRANSFER_BLOCK = """
<transfer xmlns="http://commcarehq.org/ledger/v1" dest="{case_id}" date="2000-01-02" section-id="stock">
    <entry id="{product_id}" quantity="{quantity}" />
</transfer >
"""


class LedgerTests(TestCase):

    @classmethod
    def setUpClass(cls):
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)
        cls.product = make_product(DOMAIN, 'A Product', 'prodcode')

    def setUp(self):
        self.interface = FormProcessorInterface(domain=DOMAIN)
        self.factory = CaseFactory(domain=DOMAIN)
        self.case = self.factory.create_case()

    def _submit_ledgers(self, ledger_block, quantity):
        return submit_case_blocks(
            ledger_block.format(case_id=self.case.case_id, product_id=self.product._id, quantity=quantity),
            DOMAIN
        )

    def _set_balance(self, balance):
        self._submit_ledgers(BALANCE_BLOCK, balance)

    @run_with_all_backends
    def test_balance_submission(self):
        orignal_form_count = len(self.interface.get_case_forms(self.case.case_id))
        self._submit_ledgers(BALANCE_BLOCK, 100)
        self._assert_ledger_state(100)
        # make sure the form is part of the case's history
        self.assertEqual(orignal_form_count + 1, len(self.interface.get_case_forms(self.case.case_id)))

    @run_with_all_backends
    def test_balance_submission_with_prior_balance(self):
        self._set_balance(100)
        self._assert_ledger_state(100)
        self._set_balance(50)
        self._assert_ledger_state(50)
        self._set_balance(150)
        self._assert_ledger_state(150)

    @run_with_all_backends
    def test_transfer_submission(self):
        orignal_form_count = len(self.interface.get_case_forms(self.case.case_id))
        self._submit_ledgers(TRANSFER_BLOCK, 100)
        self._assert_ledger_state(100)
        # make sure the form is part of the case's history
        self.assertEqual(orignal_form_count + 1, len(self.interface.get_case_forms(self.case.case_id)))

    @run_with_all_backends
    def test_transfer_submission_with_prior_balance(self):
        self._set_balance(100)
        self._submit_ledgers(TRANSFER_BLOCK, 100)
        self._assert_ledger_state(200)

    def _assert_ledger_state(self, expected_balance):
        ledgers = self.interface.ledger_processor.get_ledgers_for_case(self.case.case_id)
        self.assertEqual(1, len(ledgers))
        ledger = ledgers[0]
        self.assertEqual(self.case.case_id, ledger.case_id)
        self.assertEqual(self.product._id, ledger.entry_id)
        self.assertEqual('stock', ledger.section_id)
        self.assertEqual(expected_balance, ledger.balance)
