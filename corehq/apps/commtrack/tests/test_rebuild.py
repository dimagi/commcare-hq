from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from casexml.apps.case.cleanup import rebuild_case_from_forms
from casexml.apps.case.mock import CaseFactory
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.processing import rebuild_stock_state
from corehq.apps.commtrack.tests.util import get_single_balance_block
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors, CaseAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import RebuildWithReason
from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
from corehq.form_processor.tests.utils import run_with_all_backends

LEDGER_BLOCKS_SIMPLE = """
<transfer xmlns="http://commcarehq.org/ledger/v1" dest="{case_id}" date="2000-01-02" section-id="stock">
    <entry id="{product_id}" quantity="100" />
</transfer >

<balance xmlns="http://commcarehq.org/ledger/v1" entity-id="{case_id}" date="2000-01-01" section-id="stock">
    <entry id="{product_id}" quantity="100" />
</balance>
"""

LEDGER_BLOCKS_INFERRED = """
<transfer xmlns="http://commcarehq.org/ledger/v1" dest="{case_id}" date="2000-01-02" section-id="stock">
    <entry id="{product_id}" quantity="50" />
</transfer >

<balance xmlns="http://commcarehq.org/ledger/v1" entity-id="{case_id}" date="2000-01-01" section-id="stock">
    <entry id="{product_id}" quantity="100" />
</balance>
"""


class RebuildStockStateTest(TestCase):

    def setUp(self):
        super(RebuildStockStateTest, self).setUp()
        self.domain = 'asldkjf-domain'
        self.case = CaseFactory(domain=self.domain).create_case()
        self.product = make_product(self.domain, 'Product Name', 'prodcode')
        self._stock_state_key = dict(
            section_id='stock',
            case_id=self.case.case_id,
            product_id=self.product.get_id
        )
        self.unique_reference = UniqueLedgerReference(
            case_id=self.case.case_id, section_id='stock', entry_id=self.product.get_id
        )

        self.ledger_processor = FormProcessorInterface(self.domain).ledger_processor

    def _assert_stats(self, epxected_tx_count, expected_stock_state_balance, expected_tx_balance):
        ledger_value = LedgerAccessors(self.domain).get_ledger_value(**self.unique_reference._asdict())
        latest_txn = LedgerAccessors(self.domain).get_latest_transaction(**self.unique_reference._asdict())
        all_txns = LedgerAccessors(self.domain).get_ledger_transactions_for_case(**self.unique_reference._asdict())
        self.assertEqual(epxected_tx_count, len(all_txns))
        self.assertEqual(expected_stock_state_balance, ledger_value.stock_on_hand)
        self.assertEqual(expected_tx_balance, latest_txn.stock_on_hand)

    def _submit_ledgers(self, ledger_blocks):
        return submit_case_blocks(
            ledger_blocks.format(**self._stock_state_key), self.domain)[0].form_id

    @run_with_all_backends
    def test_simple(self):
        self._submit_ledgers(LEDGER_BLOCKS_SIMPLE)
        self._assert_stats(2, 100, 100)

        self.ledger_processor.rebuild_ledger_state(**self.unique_reference._asdict())

        self._assert_stats(2, 200, 200)

    def test_inferred(self):
        self._submit_ledgers(LEDGER_BLOCKS_INFERRED)
        # this is weird behavior:
        # it just doesn't process the second one
        # even though knowing yesterday's certainly changes the meaning
        # of today's transfer

        # UPDATE SK 2016-03-14: this happens because the transactions are received out of order
        # (they appear out of order in the form XML) and hence saved out of order.
        # When the older transaction is saved it will only look back in time
        # to create inferred transactions and not ahead.
        self._assert_stats(2, 50, 50)

        rebuild_stock_state(**self._stock_state_key)

        self._assert_stats(2, 150, 150)

    @run_with_all_backends
    def test_case_actions(self):
        # make sure that when a case is rebuilt (using rebuild_case)
        # stock transactions show up as well
        form_id = self._submit_ledgers(LEDGER_BLOCKS_SIMPLE)
        case_id = self.case.case_id
        rebuild_case_from_forms(self.domain, case_id, RebuildWithReason(reason='test'))
        case = CaseAccessors(self.domain).get_case(self.case.case_id)
        self.assertEqual(case.xform_ids[1:], [form_id])
        self.assertTrue(form_id in [action.form_id for action in case.actions])

    @run_with_all_backends
    def test_edit_submissions_simple(self):
        initial_quantity = 100
        form = submit_case_blocks(
            case_blocks=get_single_balance_block(quantity=initial_quantity, **self._stock_state_key),
            domain=self.domain,
        )[0]
        self._assert_stats(1, initial_quantity, initial_quantity)

        case_accessors = CaseAccessors(self.domain)
        case = case_accessors.get_case(self.case.case_id)
        try:
            self.assertTrue(any([action.is_ledger_transaction for action in case.actions]))
        except AttributeError:
            self.assertTrue('commtrack' in [action.action_type for action in case.actions])
        self.assertEqual([form.form_id], case.xform_ids[1:])

        # change the value to 50
        edit_quantity = 50
        submit_case_blocks(
            case_blocks=get_single_balance_block(quantity=edit_quantity, **self._stock_state_key),
            domain=self.domain,
            form_id=form.form_id,
        )
        case = case_accessors.get_case(self.case.case_id)

        try:
            # CaseTransaction
            self.assertTrue(any([action.is_ledger_transaction for action in case.actions]))
        except AttributeError:
            # CaseAction
            self.assertTrue('commtrack' in [action.action_type for action in case.actions])

        self._assert_stats(1, edit_quantity, edit_quantity)
        self.assertEqual([form.form_id], case.xform_ids[1:])
