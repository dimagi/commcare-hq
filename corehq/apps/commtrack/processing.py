import logging
from django.db import transaction
from django.utils.translation import ugettext as _
from casexml.apps.case.const import CASE_ACTION_COMMTRACK
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.xform import is_device_report, CaseDbCache
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from casexml.apps.stock.models import StockTransaction, StockReport
from corehq.apps.commtrack.exceptions import MissingProductId
from dimagi.utils.decorators.log_exception import log_exception
from corehq.apps.commtrack.models import xml_to_stock_report_helper
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
    if report.type == stockconst.REPORT_TYPE_BALANCE:
        txn.stock_on_hand = transaction_helper.quantity
        txn.quantity = 0
    elif report.type == stockconst.REPORT_TYPE_TRANSFER:
        previous_transaction = txn.get_previous_transaction()
        txn.quantity = transaction_helper.relative_quantity
        txn.stock_on_hand = txn.quantity + (
            previous_transaction.stock_on_hand
            if previous_transaction else 0
        )
    else:
        raise ValueError()
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
    relevant_cases = [case_db.get(case_id) for case_id in
                      set(transaction_helper.case_id
                          for transaction_helper in transaction_helpers)]

    user_id = xform.form['meta']['userID']
    submit_time = xform['received_on']

    # touch every case for proper ota restore logic syncing to be preserved
    for i, case in enumerate(relevant_cases):
        if case is None:
            raise IllegalCaseId(_('Ledger transaction references invalid Case ID "{}"'.format(case_ids[i])))

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


def unpack_commtrack(xform):
    xml = xform.get_xml_element()

    def commtrack_nodes(node):
        for child in node:
            if child.tag.startswith('{%s}' % COMMTRACK_REPORT_XMLNS):
                yield child
            else:
                for e in commtrack_nodes(child):
                    yield e

    for elem in commtrack_nodes(xml):
        yield xml_to_stock_report_helper(xform, elem)
