from collections import namedtuple
import logging
from django.db import transaction
from django.utils.translation import ugettext as _
from casexml.apps.case.const import CASE_ACTION_COMMTRACK
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.xform import is_device_report, CaseDbCache
from casexml.apps.stock.models import StockTransaction, StockReport
from corehq.apps.commtrack.exceptions import MissingProductId
from corehq.apps.commtrack.parsing import unpack_commtrack
from dimagi.utils.decorators.log_exception import log_exception
from casexml.apps.case.models import CommCareCaseAction
from casexml.apps.case.xml.parser import AbstractAction
from casexml.apps.stock import const as stockconst


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

    @transaction.atomic
    def commit(self):
        """
        Commit changes to the database
        """
        # if cases were changed we should purge the sync token cache
        # this ensures that ledger updates will sync back down
        if self.relevant_cases and self.xform.get_sync_token():
            self.xform.get_sync_token().invalidate_cached_payloads()

        # create the django models
        for stock_report_helper in self.stock_report_helpers:
            create_models_for_stock_report(self.domain, stock_report_helper)


@transaction.atomic
def create_models_for_stock_report(domain, stock_report_helper):
    """
    Save stock report and stock transaction models to the database.
    """
    assert stock_report_helper._form.domain == domain
    if stock_report_helper.tag not in stockconst.VALID_REPORT_TYPES:
        return
    report = _create_model_for_stock_report(domain, stock_report_helper)
    for transaction_helper in stock_report_helper.transactions:
        _create_model_for_stock_transaction(report, transaction_helper)


def _create_model_for_stock_report(domain, stock_report_helper):
    return StockReport.objects.create(
        form_id=stock_report_helper.form_id,
        date=stock_report_helper.timestamp,
        type=stock_report_helper.tag,
        domain=domain,
    )

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
        new_delta = 0
    elif report_type == stockconst.REPORT_TYPE_TRANSFER:
        original_balance = lazy_original_balance()
        new_delta = quantity
        new_balance = new_delta + (original_balance if original_balance else 0)
    else:
        raise ValueError()
    return LedgerValues(new_balance, new_delta)


def _create_model_for_stock_transaction(report, transaction_helper):
    assert report.type in stockconst.VALID_REPORT_TYPES
    txn = StockTransaction(
        report=report,
        case_id=transaction_helper.case_id,
        section_id=transaction_helper.section_id,
        product_id=transaction_helper.product_id,
        type=transaction_helper.action,
        subtype=transaction_helper.subaction,
    )

    def lazy_original_balance():
        previous_transaction = txn.get_previous_transaction()
        if previous_transaction:
            return previous_transaction.stock_on_hand
        else:
            return None

    new_ledger_values = compute_ledger_values(
        lazy_original_balance, report.type,
        transaction_helper.relative_quantity)

    txn.stock_on_hand = new_ledger_values.balance
    txn.quantity = new_ledger_values.delta

    if report.domain:
        # set this as a shortcut for post save signal receivers
        txn.domain = report.domain
    txn.save()
    return txn


@log_exception()
def process_stock(xform, case_db=None):
    """
    process the commtrack xml constructs in an incoming submission
    """
    case_db = case_db or CaseDbCache()
    assert isinstance(case_db, CaseDbCache)
    if is_device_report(xform):
        return StockProcessingResult(xform)

    stock_report_helpers = list(unpack_commtrack(xform))
    transaction_helpers = [
        transaction_helper
        for stock_report_helper in stock_report_helpers
        for transaction_helper in stock_report_helper.transactions
    ]

    # omitted: normalize_transactions (used for bulk requisitions?)

    if not transaction_helpers:
        return StockProcessingResult(xform)

    # validate product ids
    if any(transaction_helper.product_id in ('', None)
            for transaction_helper in transaction_helpers):
        raise MissingProductId(
            _('Product IDs must be set for all ledger updates!'))

    # list of cases that had stock reports in the form
    # there is no need to wrap them by case type
    case_ids = list(set(transaction_helper.case_id
                        for transaction_helper in transaction_helpers))
    relevant_cases = [case_db.get(case_id) for case_id in case_ids]

    user_id = xform.form['meta']['userID']
    submit_time = xform['received_on']

    # touch every case for proper ota restore logic syncing to be preserved
    for case_id, case in zip(case_ids, relevant_cases):
        if case is None:
            raise IllegalCaseId(
                _('Ledger transaction references invalid Case ID "{}"')
                .format(case_id))

        case_action = CommCareCaseAction.from_parsed_action(
            submit_time, user_id, xform, AbstractAction(CASE_ACTION_COMMTRACK)
        )
        # hack: clear the sync log id so this modification always counts
        # since consumption data could change server-side
        case_action.sync_log_id = ''
        case.actions.append(case_action)
        case_db.mark_changed(case)

    return StockProcessingResult(
        xform=xform,
        relevant_cases=relevant_cases,
        stock_report_helpers=stock_report_helpers,
    )


def _adjust_ledger_values(original_balance, stock_transaction):
    if stock_transaction.report.type == stockconst.REPORT_TYPE_BALANCE:
        quantity = stock_transaction.stock_on_hand
    elif stock_transaction.report.type == stockconst.REPORT_TYPE_TRANSFER:
        quantity = stock_transaction.quantity
    else:
        raise ValueError()

    ledger_values = compute_ledger_values(
        lambda: original_balance, stock_transaction.report.type, quantity)

    if stock_transaction.report.type == stockconst.REPORT_TYPE_BALANCE:
        assert stock_transaction.stock_on_hand == ledger_values.balance
        # this is currently always 0 because of inferred transactions
        stock_transaction.quantity = ledger_values.delta
    elif stock_transaction.report.type == stockconst.REPORT_TYPE_TRANSFER:
        stock_transaction.stock_on_hand = ledger_values.balance
        assert stock_transaction.quantity == ledger_values.delta, (stock_transaction.quantity, ledger_values.delta)
    else:
        raise ValueError()

    return ledger_values.balance


@transaction.atomic
def rebuild_stock_state(case_id, section_id, product_id):
    """
    rebuilds the StockState object
    and the quantity and stock_on_hand fields of StockTransaction
    when they are calculated from previous state
    (as opposed to part of the explict transaction)

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
            stock_transaction.delete()
        else:
            balance = _adjust_ledger_values(balance, stock_transaction)
            stock_transaction.save()
