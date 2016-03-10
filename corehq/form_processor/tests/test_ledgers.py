from collections import namedtuple

from django.conf import settings
from django.test import TestCase
from casexml.apps.case.mock import CaseFactory, CaseBlock
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import CaseTransaction
from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
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

TestLedger = namedtuple('TestLedger', ['block', 'quantity', 'product_id'])


class LedgerTests(TestCase):

    @classmethod
    def setUpClass(cls):
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)
        cls.product_a = make_product(DOMAIN, 'A Product', 'prodcode_a')
        cls.product_b = make_product(DOMAIN, 'B Product', 'prodcode_b')
        cls.product_c = make_product(DOMAIN, 'C Product', 'prodcode_c')

    def setUp(self):
        self.interface = FormProcessorInterface(domain=DOMAIN)
        self.factory = CaseFactory(domain=DOMAIN)
        self.case = self.factory.create_case()

    def _submit_ledgers(self, test_ledgers):
        return submit_case_blocks([
            ledger.block.format(
                case_id=self.case.case_id,
                product_id=ledger.product_id or self.product_a._id,
                quantity=ledger.quantity
            )
            for ledger in test_ledgers],
            DOMAIN
        )

    def _set_balance(self, balance):
        self._submit_ledgers([TestLedger(BALANCE_BLOCK, balance, None)])

    @run_with_all_backends
    def test_balance_submission(self):
        orignal_form_count = len(self.interface.get_case_forms(self.case.case_id))
        self._submit_ledgers([TestLedger(BALANCE_BLOCK, 100, None)])
        self._assert_ledger_state(100)
        # make sure the form is part of the case's history
        self.assertEqual(orignal_form_count + 1, len(self.interface.get_case_forms(self.case.case_id)))

    @run_with_all_backends
    def test_balance_submission_multiple(self):
        balances = {
            self.product_a._id: 100,
            self.product_b._id: 50,
            self.product_c._id: 25,
        }
        self._submit_ledgers([
            TestLedger(BALANCE_BLOCK, balance, prod_id)
            for prod_id, balance in balances.items()
        ])
        for prod_id, expected_balance in balances.items():
            balance = self.interface.ledger_processor.get_current_ledger_value(
                UniqueLedgerReference(
                case_id=self.case.case_id,
                section_id='stock',
                entry_id=prod_id
            ))
            self.assertEqual(expected_balance, balance)

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
        self._submit_ledgers([TestLedger(TRANSFER_BLOCK, 100, None)])
        self._assert_ledger_state(100)
        # make sure the form is part of the case's history
        self.assertEqual(orignal_form_count + 1, len(self.interface.get_case_forms(self.case.case_id)))

    @run_with_all_backends
    def test_transfer_submission_with_prior_balance(self):
        self._set_balance(100)
        self._submit_ledgers([TestLedger(TRANSFER_BLOCK, 100, None)])
        self._assert_ledger_state(200)

    @run_with_all_backends
    def test_ledger_update_with_case_update(self):
        submit_case_blocks([
            CaseBlock(case_id=self.case.case_id, update={'a': "1"}).as_string(),
            BALANCE_BLOCK.format(
                case_id=self.case.case_id,
                product_id=self.product_a._id,
                quantity=100
            )],
            DOMAIN
        )

        self._assert_ledger_state(100)
        case = CaseAccessors(DOMAIN).get_case(self.case.case_id)
        self.assertEqual("1", case.dynamic_case_properties()['a'])
        if settings.TESTS_SHOULD_USE_SQL_BACKEND:
            transactions = CaseAccessorSQL.get_transactions(self.case.case_id)
            self.assertEqual(2, len(transactions))
            self.assertTrue(transactions[0].is_form_transaction)
            # ordering not guaranteed since they have the same date
            self.assertTrue(transactions[1].is_form_transaction)
            self.assertTrue(transactions[1].is_ledger_transaction)

    def _assert_ledger_state(self, expected_balance):
        ledgers = self.interface.ledger_processor.get_ledgers_for_case(self.case.case_id)
        self.assertEqual(1, len(ledgers))
        ledger = ledgers[0]
        self.assertEqual(self.case.case_id, ledger.case_id)
        self.assertEqual(self.product_a._id, ledger.entry_id)
        self.assertEqual('stock', ledger.section_id)
        self.assertEqual(expected_balance, ledger.balance)
