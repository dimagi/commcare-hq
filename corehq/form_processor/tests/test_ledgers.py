from collections import namedtuple

from django.conf import settings
from django.test import TestCase
from casexml.apps.case.mock import CaseFactory, CaseBlock
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, LedgerAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import LedgerTransaction
from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
from corehq.form_processor.tests import FormProcessorTestUtils, run_with_all_backends
from corehq.form_processor.utils.general import should_use_sql_backend

DOMAIN = 'ledger-tests'
TransactionValues = namedtuple('TransactionValues', ['type', 'product_id', 'delta', 'updated_balance'])


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

    def _submit_ledgers(self, ledger_blocks):
        return submit_case_blocks(ledger_blocks, DOMAIN)

    def _set_balance(self, balance):
        from corehq.apps.commtrack.tests import get_single_balance_block
        self._submit_ledgers([
            get_single_balance_block(self.case.case_id, self.product_a._id, balance)
        ])

    def _transfer_in(self, amount):
        from corehq.apps.commtrack.tests.util import get_single_transfer_block
        self._submit_ledgers([
            get_single_transfer_block(None, self.case.case_id, self.product_a._id, amount)
        ])

    def _transfer_out(self, amount):
        from corehq.apps.commtrack.tests.util import get_single_transfer_block
        self._submit_ledgers([
            get_single_transfer_block(self.case.case_id, None, self.product_a._id, amount)
        ])

    @run_with_all_backends
    def test_balance_submission(self):
        orignal_form_count = len(self.interface.get_case_forms(self.case.case_id))
        self._set_balance(100)
        self._assert_ledger_state(100)
        # make sure the form is part of the case's history
        self.assertEqual(orignal_form_count + 1, len(self.interface.get_case_forms(self.case.case_id)))
        self._assert_transactions([
            self._expected_val(100, 100)
        ])

    @run_with_all_backends
    def test_balance_submission_multiple(self):
        from corehq.apps.commtrack.tests import get_single_balance_block
        balances = {
            self.product_a._id: 100,
            self.product_b._id: 50,
            self.product_c._id: 25,
        }
        self._submit_ledgers([
            get_single_balance_block(self.case.case_id, prod_id, balance)
            for prod_id, balance in balances.items()
        ])
        expected_transactions = []
        for prod_id, expected_balance in balances.items():
            expected_transactions.append(self._expected_val(
                expected_balance, expected_balance, product_id=prod_id
            ))
            balance = self.interface.ledger_db.get_current_ledger_value(
                UniqueLedgerReference(
                case_id=self.case.case_id,
                section_id='stock',
                entry_id=prod_id
            ))
            self.assertEqual(expected_balance, balance)

        self._assert_transactions(expected_transactions, ignore_ordering=True)

    @run_with_all_backends
    def test_balance_submission_with_prior_balance(self):
        self._set_balance(100)
        self._assert_ledger_state(100)
        self._set_balance(50)
        self._assert_ledger_state(50)
        self._set_balance(150)
        self._assert_ledger_state(150)

        self._assert_transactions([
            self._expected_val(100, 100),
            self._expected_val(-50, 50),
            self._expected_val(100, 150),
        ])

    @run_with_all_backends
    def test_transfer_submission(self):
        orignal_form_count = len(self.interface.get_case_forms(self.case.case_id))
        self._transfer_in(100)
        self._assert_ledger_state(100)
        # make sure the form is part of the case's history
        self.assertEqual(orignal_form_count + 1, len(self.interface.get_case_forms(self.case.case_id)))

        self._assert_transactions([
            self._expected_val(100, 100, type_=LedgerTransaction.TYPE_TRANSFER),
        ])

    @run_with_all_backends
    def test_transfer_submission_with_prior_balance(self):
        self._set_balance(100)
        self._transfer_in(100)
        self._assert_ledger_state(200)

        self._assert_transactions([
            self._expected_val(100, 100),
            self._expected_val(100, 200, type_=LedgerTransaction.TYPE_TRANSFER),
        ])

    @run_with_all_backends
    def test_full_combination(self):
        self._set_balance(100)
        self._transfer_in(100)
        self._assert_ledger_state(200)
        self._transfer_out(20)
        self._assert_ledger_state(180)
        self._set_balance(150)
        self._set_balance(170)
        self._transfer_out(30)
        self._assert_ledger_state(140)

        self._assert_transactions([
            self._expected_val(100, 100),
            self._expected_val(100, 200, type_=LedgerTransaction.TYPE_TRANSFER),
            self._expected_val(-20, 180, type_=LedgerTransaction.TYPE_TRANSFER),
            self._expected_val(-30, 150),
            self._expected_val(20, 170),
            self._expected_val(-30, 140, type_=LedgerTransaction.TYPE_TRANSFER),
        ])

    @run_with_all_backends
    def test_ledger_update_with_case_update(self):
        from corehq.apps.commtrack.tests import get_single_balance_block
        submit_case_blocks([
            CaseBlock(case_id=self.case.case_id, update={'a': "1"}).as_string(),
            get_single_balance_block(self.case.case_id, self.product_a._id, 100)],
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

        self._assert_transactions([
            self._expected_val(100, 100),
        ])

    def _assert_ledger_state(self, expected_balance):
        ledgers = self.interface.ledger_db.get_ledgers_for_case(self.case.case_id)
        self.assertEqual(1, len(ledgers))
        ledger = ledgers[0]
        self.assertEqual(self.case.case_id, ledger.case_id)
        self.assertEqual(self.product_a._id, ledger.entry_id)
        self.assertEqual('stock', ledger.section_id)
        self.assertEqual(expected_balance, ledger.balance)

    def _assert_transactions(self, values, ignore_ordering=False):
        if should_use_sql_backend(DOMAIN):
            txs = LedgerAccessorSQL.get_ledger_transactions_for_case(self.case.case_id)
            self.assertEqual(len(values), len(txs))
            if ignore_ordering:
                values = sorted(values, key=lambda v: (v.type, v.product_id))
                txs = sorted(txs, key=lambda t: (t.type, t.entry_id))
            for expected, tx in zip(values, txs):
                self.assertEqual(expected.type, tx.type)
                self.assertEqual(expected.product_id, tx.entry_id)
                self.assertEqual('stock', tx.section_id)
                self.assertEqual(expected.delta, tx.delta)
                self.assertEqual(expected.updated_balance, tx.updated_balance)

    def _expected_val(self, delta, updated_balance, type_=LedgerTransaction.TYPE_BALANCE, product_id=None):
        return TransactionValues(type_, product_id or self.product_a._id, delta, updated_balance)
