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
from dimagi.utils.couch.loosechange import map_reduce
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
    domain = domain
    if stock_report_helper.tag not in stockconst.VALID_REPORT_TYPES:
        return
    report = StockReport.objects.create(
        form_id=stock_report_helper.form_id,
        date=stock_report_helper.timestamp,
        type=stock_report_helper.tag,
        domain=domain,
    )
    for txn in stock_report_helper.transactions:
        db_txn = StockTransaction(
            report=report,
            case_id=txn.case_id,
            section_id=txn.section_id,
            product_id=txn.product_id,
        )
        if domain:
            # set this as a shortcut for post save signal receivers
            db_txn.domain = domain
        db_txn.type = txn.action
        db_txn.subtype = txn.subaction
        if stock_report_helper.tag == stockconst.REPORT_TYPE_BALANCE:
            db_txn.stock_on_hand = txn.quantity
            db_txn.quantity = 0
        else:
            assert stock_report_helper.tag == stockconst.REPORT_TYPE_TRANSFER
            previous_transaction = db_txn.get_previous_transaction()
            db_txn.quantity = txn.relative_quantity
            db_txn.stock_on_hand = db_txn.quantity + (
                previous_transaction.stock_on_hand
                if previous_transaction else 0
            )
        db_txn.save()


@log_exception()
def process_stock(xform, case_db=None):
    """
    process the commtrack xml constructs in an incoming submission
    """
    case_db = case_db or CaseDbCache()
    assert isinstance(case_db, CaseDbCache)
    if is_device_report(xform):
        return StockProcessingResult(xform)

    # these are the raw stock report objects from the xml
    stock_reports = list(unpack_commtrack(xform))
    # flattened transaction list spanning all stock reports in the form
    transactions = [t for r in stock_reports for t in r.transactions]
    # omitted: normalize_transactions (used for bulk requisitions?)

    if not transactions:
        return StockProcessingResult(xform)

    # validate product ids
    is_empty = lambda product_id: product_id is None or product_id == ''
    if any([is_empty(tx.product_id) for tx in transactions]):
        raise MissingProductId(
            _('Product IDs must be set for all ledger updates!'))
    # transactions grouped by case/product id
    grouped_tx = map_reduce(lambda tx: [((tx.case_id, tx.product_id),)],
                            lambda v: sorted(v, key=lambda tx: tx.timestamp),
                            data=transactions,
                            include_docs=True)

    case_ids = list(set(k[0] for k in grouped_tx))
    # list of cases that had stock reports in the form
    # there is no need to wrap them by case type
    relevant_cases = [case_db.get(case_id) for case_id in case_ids]

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
        stock_report_helpers=stock_reports,
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
