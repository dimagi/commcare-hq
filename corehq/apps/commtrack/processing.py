from decimal import Decimal
import logging
from django.db import transaction
from django.utils.translation import ugettext as _
from casexml.apps.case.const import CASE_ACTION_COMMTRACK
from casexml.apps.case.xform import is_device_report, CaseDbCache
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from casexml.apps.stock.models import StockTransaction, StockReport
from corehq.apps.commtrack import const
from corehq.apps.commtrack.const import StockActions
from corehq.apps.commtrack.exceptions import MissingProductId
from corehq.apps.commtrack.models import CommtrackActionConfig
from corehq.apps.commtrack.xmlutil import XML
from corehq.apps.products.models import Product
from dimagi.utils import parsing as dateparse
from dimagi.utils.dates import force_to_datetime
from dimagi.utils.decorators.log_exception import log_exception
from dimagi.utils.couch.loosechange import map_reduce
from casexml.apps.case.models import CommCareCaseAction
from casexml.apps.case.xml.parser import AbstractAction
from casexml.apps.stock import const as stockconst, const


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
            create_models_for_stock_report(stock_report_helper)


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
    for case in relevant_cases:
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


def xml_to_stock_report_helper(form, elem):
    tag = elem.tag
    tag = tag[tag.find('}') + 1:]  # strip out ns
    timestamp = force_to_datetime(
        elem.attrib.get('date') or form.received_on).replace(tzinfo=None)
    products = elem.findall('./{%s}entry' % stockconst.COMMTRACK_REPORT_XMLNS)
    transactions = [
        t for prod_entry in products for t in
        _xml_to_stock_transaction_helper(form.domain, timestamp, tag, elem,
                                         prod_entry)
    ]

    return StockReportHelper(form, timestamp, tag, transactions)


def _xml_to_stock_transaction_helper(domain, timestamp, action_tag,
                                     action_node, product_node):
    action_type = action_node.attrib.get('type')
    subaction = action_type
    product_id = product_node.attrib.get('id')

    def _txn(action, case_id, section_id, quantity):
        # warning: here be closures
        return StockTransactionHelper(
            domain=domain,
            timestamp=timestamp,
            product_id=product_id,
            quantity=Decimal(str(quantity)) if quantity is not None else None,
            action=action,
            case_id=case_id,
            section_id=section_id,
            subaction=subaction if subaction and subaction != action else None
            # note: no location id
        )

    def _yield_txns(section_id, quantity):
        # warning: here be closures
        if action_tag == 'balance':
            case_id = action_node.attrib['entity-id']
            yield _txn(
                action=(const.StockActions.STOCKONHAND if quantity > 0
                        else const.StockActions.STOCKOUT),
                case_id=case_id,
                section_id=section_id,
                quantity=quantity,
            )
        elif action_tag == 'transfer':
            src, dst = [action_node.attrib.get(k) for k in ('src', 'dest')]
            assert src or dst
            if src is not None:
                yield _txn(action=const.StockActions.CONSUMPTION, case_id=src,
                           section_id=section_id, quantity=quantity)
            if dst is not None:
                yield _txn(action=const.StockActions.RECEIPTS, case_id=dst,
                           section_id=section_id, quantity=quantity)

    def _quantity_or_none(value, section_id):
        try:
            return float(value)
        except (ValueError, TypeError):
            logging.error((
                "Non-numeric quantity submitted on domain %s for "
                "a %s ledger" % (domain, section_id)
            ))
            return None

    section_id = action_node.attrib.get('section-id', None)
    grouped_entries = section_id is not None
    if grouped_entries:
        quantity = _quantity_or_none(
            product_node.attrib.get('quantity'),
            section_id
        )
        # make sure quantity is not an empty, unset node value
        if quantity is not None:
            for txn in _yield_txns(section_id, quantity):
                yield txn
    else:
        values = [child for child in product_node]
        for value in values:
            section_id = value.attrib.get('section-id')
            quantity = _quantity_or_none(
                value.attrib.get('quantity'),
                section_id
            )
            # make sure quantity is not an empty, unset node value
            if quantity is not None:
                for txn in _yield_txns(section_id, quantity):
                    yield txn


class StockReportHelper(object):
    """
    Intermediate class for dealing with stock XML
    """

    def __init__(self, form, timestamp, tag, transactions):
        self._form = form
        self.form_id = form._id
        self.timestamp = timestamp
        self.tag = tag
        self.transactions = transactions


class StockTransactionHelper(object):
    """
    Helper class for transactions
    """

    def __init__(self, product_id=None, action=None, subaction=None,
                 domain=None, quantity=None, location_id=None, timestamp=None,
                 case_id=None, section_id=None):
        self.quantity = quantity
        self.location_id = location_id
        self.timestamp = timestamp
        self.case_id = case_id
        self.section_id = section_id
        self.domain = domain
        self.action = action
        self.subaction = subaction
        self.product_id = product_id

    @property
    def relative_quantity(self):
        """
        Gets the quantity of this transaction as a positive or negative number
        depending on the action/context
        """
        if self.action == const.StockActions.CONSUMPTION:
            return -self.quantity
        else:
            return self.quantity

    def action_config(self, commtrack_config):
        action = CommtrackActionConfig(action=self.action,
                                       subaction=self.subaction)
        for a in commtrack_config.all_actions:
            if a.name == action.name:
                return a
        return None

    @property
    def date(self):
        if self.timestamp:
            return dateparse.json_format_datetime(self.timestamp)

    def to_xml(self, E=None, **kwargs):
        if not E:
            E = XML()

        return E.entry(
            id=self.product_id,
            quantity=str(self.quantity if self.action != StockActions.STOCKOUT
                         else 0),
        )

    @property
    def category(self):
        return 'stock'

    def fragment(self):
        """
        A short string representation of this to be used in sms correspondence
        """
        if self.quantity is not None:
            quant = self.quantity
        else:
            quant = ''
        # FIXME product fetch here is inefficient
        return '%s%s' % (Product.get(self.product_id).code.lower(), quant)

    def __repr__(self):
        return '{action} ({subaction}): {quantity} (loc: {location_id}, product: {product_id})'.format(
            action=self.action,
            subaction=self.subaction,
            quantity=self.quantity,
            location_id=self.location_id,
            product_id=self.product_id,
        )
