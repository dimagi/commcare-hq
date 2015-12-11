from collections import namedtuple
import logging

from django.db import transaction
from django.utils.translation import ugettext as _
from dimagi.utils.decorators.log_exception import log_exception

from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.stock.models import StockTransaction
from corehq.form_processor.casedb_base import AbstractCaseDbCache
from corehq.form_processor.interfaces.ledger_processor import LedgerDB
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from casexml.apps.stock import const as stockconst
from corehq.form_processor.parsers.ledgers import get_stock_actions


logger = logging.getLogger('commtrack.incoming')

COMMTRACK_LEGACY_REPORT_XMLNS = 'http://commtrack.org/legacy/stock_report'


class StockProcessingResult(object):
    """
    An object used to collect the changes that are made during stock
    processing so that they can be made more atomic
    """

    def __init__(self, xform, relevant_cases=None, stock_report_helpers=None):
        self.domain = xform.domain
        self.xform = xform
        self.relevant_cases = relevant_cases or []
        self.stock_report_helpers = stock_report_helpers or []

    def get_models_to_save(self):
        processor = FormProcessorInterface(domain=self.domain).ledger_processor
        ledger_db = LedgerDB(processor=processor)
        update_results = []

        for stock_report_helper in self.stock_report_helpers:
            this_result = processor.get_models_to_update(stock_report_helper, ledger_db)
            if this_result:
                update_results.append(this_result)
        return update_results

    def finalize(self):
        """
        Finalize anything else that needs to happen - this runs after models are saved.
        """
        # if cases were changed we should purge the sync token cache
        # this ensures that ledger updates will sync back down
        if self.relevant_cases and self.xform.get_sync_token():
            self.xform.get_sync_token().invalidate_cached_payloads()


LedgerValues = namedtuple('LedgerValues', ['balance', 'delta'])


def compute_ledger_values(lazy_original_balance, report_type, quantity):
    """
    lazy_original_balance:
        a zero-argument function returning original balance
        the original_balance is only used in the case of a transfer
        and it may be computationally expensive for the caller to provide
        putting it behind a function lets compute_ledger_values decide
        whether it's necessary to do that work
    report_type:
        a string in VALID_REPORT_TYPES
        says whether it's a transfer or balance
    quantity:
        the associated quantity, interpreted as a delta for transfers
        and a total balance for balances

    """
    if report_type == stockconst.REPORT_TYPE_BALANCE:
        new_balance = quantity
        # this is currently always 0 because of inferred transactions
        new_delta = 0
    elif report_type == stockconst.REPORT_TYPE_TRANSFER:
        original_balance = lazy_original_balance()
        new_delta = quantity
        new_balance = new_delta + (original_balance if original_balance else 0)
    else:
        raise ValueError()
    return LedgerValues(new_balance, new_delta)


@log_exception()
def process_stock(xforms, case_db=None):
    """
    process the commtrack xml constructs in an incoming submission
    """
    if not case_db:
        case_db = FormProcessorInterface(xforms[0].domain).casedb_cache()
    else:
        assert isinstance(case_db, AbstractCaseDbCache)

    stock_report_helpers = []
    case_action_intents = []
    sorted_forms = sorted(xforms, key=lambda f: 0 if f.is_deprecated else 1)
    for xform in sorted_forms:
        actions_for_form = get_stock_actions(xform)
        stock_report_helpers += actions_for_form.stock_report_helpers
        case_action_intents += actions_for_form.case_action_intents

    # validate the parsed transactions
    for stock_report_helper in stock_report_helpers:
        stock_report_helper.validate()

    relevant_cases = mark_cases_changed(case_action_intents, case_db)
    return StockProcessingResult(
        xform=sorted_forms[-1],
        relevant_cases=relevant_cases,
        stock_report_helpers=stock_report_helpers,
    )


def mark_cases_changed(case_action_intents, case_db):
    relevant_cases = []
    # touch every case for proper ota restore logic syncing to be preserved
    for action_intent in case_action_intents:
        case_id = action_intent.case_id
        case = case_db.get(action_intent.case_id)
        relevant_cases.append(case)
        if case is None:
            raise IllegalCaseId(
                _('Ledger transaction references invalid Case ID "{}"')
                .format(case_id))

        case_db.apply_action_intent(case, action_intent)
        case_db.mark_changed(case)

    return relevant_cases


def _compute_ledger_values(original_balance, stock_transaction):
    if stock_transaction.report.type == stockconst.REPORT_TYPE_BALANCE:
        quantity = stock_transaction.stock_on_hand
    elif stock_transaction.report.type == stockconst.REPORT_TYPE_TRANSFER:
        quantity = stock_transaction.quantity
    else:
        raise ValueError()

    ledger_values = compute_ledger_values(
        lambda: original_balance, stock_transaction.report.type, quantity)

    # check that the reported value (either transfer quantity or balance)
    # is not being changed; don't know why it would be, but that would be
    # a red flag
    if stock_transaction.report.type == stockconst.REPORT_TYPE_BALANCE:
        assert stock_transaction.stock_on_hand == ledger_values.balance
    elif stock_transaction.report.type == stockconst.REPORT_TYPE_TRANSFER:
        assert stock_transaction.quantity == ledger_values.delta, \
            (stock_transaction.quantity, ledger_values.delta)
    else:
        raise ValueError()

    return ledger_values

_DeleteStockTransaction = namedtuple(
    '_DeleteStockTransaction', ['stock_transaction'])
_SaveStockTransaction = namedtuple(
    '_SaveStockTransaction',
    ['stock_transaction', 'previous_ledger_values', 'ledger_values'])


def plan_rebuild_stock_state(case_id, section_id, product_id):
    """
    planner for rebuild_stock_state

    yields actions for rebuild_stock_state to take,
    facilitating doing a dry run

    Warning: since some important things are still done through signals
    rather than here explicitly, there may be some effects that aren't
    represented in the plan. For example, inferred transaction creation
    will not be represented, nor will updates to the StockState object.

    """

    # these come out latest first, so reverse them below
    stock_transactions = (
        StockTransaction
        .get_ordered_transactions_for_stock(
            case_id=case_id, section_id=section_id, product_id=product_id)
        .reverse()  # we want earliest transactions first
        .select_related('report__type')
    )
    balance = None
    for stock_transaction in stock_transactions:
        if stock_transaction.subtype == stockconst.TRANSACTION_SUBTYPE_INFERRED:
            yield _DeleteStockTransaction(stock_transaction)
        else:
            before = LedgerValues(balance=stock_transaction.stock_on_hand,
                                  delta=stock_transaction.quantity)
            after = _compute_ledger_values(balance, stock_transaction)
            # update balance for the next iteration
            balance = after.balance
            yield _SaveStockTransaction(stock_transaction, before, after)


@transaction.atomic
def rebuild_stock_state(case_id, section_id, product_id):
    """
    rebuilds the StockState object
    and the quantity and stock_on_hand fields of StockTransaction
    when they are calculated from previous state
    (as opposed to part of the explict transaction)
    """

    for action in plan_rebuild_stock_state(case_id, section_id, product_id):
        if isinstance(action, _DeleteStockTransaction):
            action.stock_transaction.delete()
        elif isinstance(action, _SaveStockTransaction):
            action.stock_transaction.stock_on_hand = action.ledger_values.balance
            action.stock_transaction.quantity = action.ledger_values.delta
            action.stock_transaction.save()
        else:
            raise ValueError()
