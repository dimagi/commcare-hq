from django.test import TestCase
from casexml.apps.case.cleanup import rebuild_case
from casexml.apps.case.models import CommCareCase
from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.models import StockState
from corehq.apps.commtrack.processing import rebuild_stock_state
from corehq.apps.commtrack.tests.util import get_single_balance_block
from corehq.apps.hqcase.utils import submit_case_blocks


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
        self.domain = 'asldkjf-domain'
        self.case = CommCareCase(domain=self.domain)
        self.case.save()
        self.product = make_product(self.domain, 'Product Name', 'prodcode')
        self._stock_state_key = dict(
            section_id='stock',
            case_id=self.case.get_id,
            product_id=self.product.get_id
        )

    def _get_stats(self):
        stock_state = StockState.objects.get(**self._stock_state_key)
        latest_txn = StockTransaction.latest(**self._stock_state_key)
        all_txns = StockTransaction.get_ordered_transactions_for_stock(
            **self._stock_state_key)
        return stock_state, latest_txn, all_txns

    def _submit_ledgers(self, ledger_blocks):
        return submit_case_blocks(
            ledger_blocks.format(**self._stock_state_key), self.domain)

    def test_simple(self):
        self._submit_ledgers(LEDGER_BLOCKS_SIMPLE)
        stock_state, latest_txn, all_txns = self._get_stats()
        self.assertEqual(stock_state.stock_on_hand, 100)
        self.assertEqual(latest_txn.stock_on_hand, 100)
        self.assertEqual(all_txns.count(), 2)

        rebuild_stock_state(**self._stock_state_key)

        stock_state, latest_txn, all_txns = self._get_stats()
        self.assertEqual(stock_state.stock_on_hand, 200)
        self.assertEqual(latest_txn.stock_on_hand, 200)
        self.assertEqual(all_txns.count(), 2)

    def test_inferred(self):
        self._submit_ledgers(LEDGER_BLOCKS_INFERRED)
        stock_state, latest_txn, all_txns = self._get_stats()
        # this is weird behavior:
        # it just doesn't process the second one
        # even though knowing yesterday's certainly changes the meaning
        # of today's transfer
        self.assertEqual(stock_state.stock_on_hand, 50)
        self.assertEqual(latest_txn.stock_on_hand, 50)
        self.assertEqual(all_txns.count(), 3)

        rebuild_stock_state(**self._stock_state_key)

        stock_state, latest_txn, all_txns = self._get_stats()

        self.assertEqual(stock_state.stock_on_hand, 150)
        self.assertEqual(latest_txn.stock_on_hand, 150)
        self.assertEqual(all_txns.count(), 2)

    def test_case_actions(self):
        """
        make sure that when a case is rebuilt (using rebuild_case)
        stock transactions show up as well
        """
        form_id = self._submit_ledgers(LEDGER_BLOCKS_SIMPLE)
        case_id = self.case.case_id
        rebuild_case(case_id)
        case = CommCareCase.get(case_id)
        self.assertEqual(case.xform_ids, [form_id])
        self.assertEqual(case.actions[0].xform_id, form_id)

    def test_edit_submissions_simple(self):
        initial_quantity = 100
        form_id = submit_case_blocks(
            case_blocks=get_single_balance_block(quantity=initial_quantity, **self._stock_state_key),
            domain=self.domain,
        )
        stock_state, latest_txn, all_txns = self._get_stats()
        self.assertEqual(stock_state.stock_on_hand, initial_quantity)
        self.assertEqual(latest_txn.stock_on_hand, initial_quantity)
        self.assertEqual(all_txns.count(), 1)

        # change the value to 50
        edit_quantity = 50
        submit_case_blocks(
            case_blocks=get_single_balance_block(quantity=edit_quantity, **self._stock_state_key),
            domain=self.domain,
            form_id=form_id,
        )
        stock_state, latest_txn, all_txns = self._get_stats()
        self.assertEqual(stock_state.stock_on_hand, edit_quantity)
        self.assertEqual(latest_txn.stock_on_hand, edit_quantity)
        self.assertEqual(all_txns.count(), 1)
