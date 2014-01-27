from decimal import Decimal
import logging
from casexml.apps.stock.const import TRANSACTION_SUBTYPE_INFERRED
from dimagi.utils.decorators.log_exception import log_exception
from corehq.apps.commtrack.models import CommtrackConfig, StockTransaction, SupplyPointCase, NewStockReport, SupplyPointProductCase
from corehq.apps.commtrack import const
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.commtrack.util import wrap_commtrack_case
from corehq.apps.commtrack.xmlutil import XML
from casexml.apps.case.models import CommCareCaseAction, CommCareCase
from casexml.apps.case.xml.parser import AbstractAction

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from xml import etree as legacy_etree
from datetime import date
from lxml import etree
from corehq.apps.receiverwrapper.util import submit_form_locally
from dimagi.utils.parsing import string_to_datetime


logger = logging.getLogger('commtrack.incoming')

COMMTRACK_LEGACY_REPORT_XMLNS = 'http://commtrack.org/legacy/stock_report'

@log_exception()
def process_stock(sender, xform, config=None, **kwargs):
    """
    process the commtrack xml constructs in an incoming submission
    """
    domain = xform.domain

    config = CommtrackConfig.for_domain(domain)

    # these are the raw stock report objects from the xml
    stock_reports = list(unpack_commtrack(xform, config))
    # flattened transaction list spanning all stock reports in the form
    transactions = [t for r in stock_reports for t in r.transactions]
    # omitted: normalize_transactions (used for bulk requisitions?)

    if not transactions:
        return

    # transactions grouped by case/product id
    grouped_tx = map_reduce(lambda tx: [((tx.case_id, tx.product_id),)],
                            lambda v: sorted(v, key=lambda tx: tx.timestamp),
                            data=transactions,
                            include_docs=True)

    # list of cases that had stock reports in the form, properly wrapped by case type
    relevant_cases = [wrap_commtrack_case(result['doc']) for result in
                      CommCareCase.get_db().view('_all_docs',
                                                 keys=list(set(k[0] for k in grouped_tx)),
                                                 include_docs=True)]
    user_id = xform.form['meta']['userID']
    submit_time = xform['received_on']

    # touch every case for proper ota restore logic syncing to be preserved
    # todo: confirm this is necessary
    for case in relevant_cases:
        case_action = CommCareCaseAction.from_parsed_action(submit_time, user_id, xform, AbstractAction('commtrack'))
        case.actions.append(case_action)
        case.save()

    def _is_stockonhand_txn(txn):
        return txn.section_id == 'stock'

    # supply point cases have to be handled differently because of the use of product subcases
    supply_point_cases = filter(lambda case: isinstance(case, SupplyPointCase), relevant_cases)
    if supply_point_cases:
        def _do_legacy_xml_submission():
            supply_point_product_subcases = dict((sp._id, product_subcases(sp)) for sp in supply_point_cases)
            post_processed_transactions = []
            E = XML(ns=COMMTRACK_LEGACY_REPORT_XMLNS)
            root = E.commtrack_data()

            for (case_id, product_id), txs in grouped_tx.iteritems():
                # filter out non-stockonhand transactions first
                txs = filter(_is_stockonhand_txn, txs)
                if case_id in supply_point_product_subcases:
                    subcase = supply_point_product_subcases[case_id][product_id]
                    case_block, reconciliations = process_product_transactions(user_id, submit_time, subcase, txs)
                    root.append(case_block)
                    post_processed_transactions.extend(reconciliations)

            supply_point_ids = supply_point_product_subcases.keys()
            supply_point_transactions = filter(lambda tx: _is_stockonhand_txn(tx) and tx.case_id in supply_point_ids, transactions)
            post_processed_transactions.extend(map(lambda tx: LegacyStockTransaction.convert(tx, supply_point_product_subcases), supply_point_transactions))

            # only bother with submission if there were any actual transactions
            if post_processed_transactions:
                set_transactions(root, post_processed_transactions, E)
                submission = etree.tostring(root, encoding='utf-8', pretty_print=True)
                logger.debug(submission)
                submit_form_locally(submission, domain,
                                    received_on=string_to_datetime(submit_time))

        _do_legacy_xml_submission()

    # create the django models
    for report in stock_reports:
        report.create_models()


# TODO retire this with move to new data model
def product_subcases(supply_point):
    """
    given a supply point, return all the sub-cases for each product stocked at that supply point
    actually returns a mapping: product doc id => sub-case
    ACTUALLY returns a dict that will create non-existent product sub-cases on demand
    """
    from helpers import make_supply_point_product

    product_subcases = supply_point.get_product_subcases()
    product_subcase_mapping = dict((subcase.product, subcase) for subcase in product_subcases)

    def create_product_subcase(product_uuid):
        return make_supply_point_product(supply_point, product_uuid)

    class DefaultDict(dict):
        """similar to collections.defaultdict(), but factory function has access
        to 'key'
        """
        def __init__(self, factory, *args, **kwargs):
            super(DefaultDict, self).__init__(*args, **kwargs)
            self.factory = factory

        def __getitem__(self, key):
            if key in self:
                val = self.get(key)
            else:
                val = self.factory(key)
                self[key] = val
            return val

    return DefaultDict(create_product_subcase, product_subcase_mapping)

def unpack_commtrack(xform, config):
    xml = etree.fromstring(xform.get_xml())

    def commtrack_nodes(node):
        for child in node:
            if child.tag.startswith('{%s}' % const.COMMTRACK_REPORT_XMLNS):
                yield child
            else:
                for e in commtrack_nodes(child):
                    yield e

    for elem in commtrack_nodes(xml):
        yield NewStockReport.from_xml(xform, config, elem)


def set_transactions(root, new_tx, E):
    for tx in new_tx:
        root.append(tx.to_legacy_xml(E))

def process_product_transactions(user_id, timestamp, case, txs):
    """
    process all the transactions from a stock report for an individual
    product. we have to apply them in bulk because each one may update
    the case state that the next one works off of. therefore we have to
    keep track of the updated case state ourselves
    """
    current_state = StockState(case, timestamp)
    reconciliations = []

    i = [0] # annoying python 2.x scope issue
    def set_order(tx):
        tx.processing_order = i[0]
        i[0] += 1

    for tx in txs:
        recon = current_state.update(tx.action, tx.quantity)
        if recon:
            set_order(recon)
            reconciliations.append(recon)
        set_order(tx)
    return current_state.to_case_block(user_id=user_id), reconciliations

from couchdbkit.ext.django.schema import *
class LegacyStockTransaction(StockTransaction):
    product_subcase = StringProperty()

    def to_legacy_xml(self, E):
        attr = {}
        if self.subaction == TRANSACTION_SUBTYPE_INFERRED:
            attr['inferred'] = 'true'
        if self.processing_order is not None:
            attr['order'] = str(self.processing_order + 1)

        return E.transaction(
            E.product(self.product_id),
            E.product_entry(self.product_subcase),
            E.action((self.subaction if self.subaction != TRANSACTION_SUBTYPE_INFERRED else None) or self.action),
            E.value(str(self.quantity)),
            **attr
        )

    @classmethod
    def convert(cls, tx, product_subcases):
        ltx = LegacyStockTransaction(**dict(tx.iteritems()))
        ltx.product_subcase = product_subcases[tx.case_id][tx.product_id]._id
        return ltx

class StockState(object):
    def __init__(self, case, reported_on):
        assert isinstance(case, SupplyPointProductCase)
        self.case = case
        self.last_reported = reported_on
        self.current_stock = case.current_stock if case.current_stock is not None else Decimal(0.0)
        self.stocked_out_since = case.stocked_out_since

    def update(self, action_type, value):
        """
        given the current stock state for a product at a location, update
        with the incoming datapoint
        
        fancy business logic to reconcile stock reports lives HERE
        """
        reconciliation_transaction = None
        def mk_reconciliation(diff):
            return LegacyStockTransaction(
                product_id=self.case.product,
                product_subcase=self.case._id,
                action=const.StockActions.RECEIPTS if diff > 0 else const.StockActions.CONSUMPTION,
                quantity=abs(diff),
                inferred=True,
            )

        if action_type == const.StockActions.STOCKOUT:
            if self.current_stock > 0:
                reconciliation_transaction = mk_reconciliation(-self.current_stock)

            self.current_stock = 0
            if not self.stocked_out_since:
                self.stocked_out_since = date.today()

        else:
            # annoying float/decimal conversion issues
            value = Decimal(value)
            if action_type == const.StockActions.STOCKONHAND:
                if self.current_stock != value:
                    reconciliation_transaction = mk_reconciliation(value - self.current_stock)
                self.current_stock = value
            elif action_type == const.StockActions.RECEIPTS:
                self.current_stock += value
            elif action_type == const.StockActions.CONSUMPTION:
                self.current_stock -= value

            # data normalization
            if self.current_stock > 0:
                self.stocked_out_since = None
            else:
                self.current_stock = 0  # handle if negative
                if not self.stocked_out_since:  # handle if stocked out date already set
                    self.stocked_out_since = date.today()

        return reconciliation_transaction

    def to_case_block(self, user_id=None):
        def convert_prop(val):
            return str(val) if val is not None else ''

        props = ['current_stock', 'stocked_out_since', 'last_reported']

        case_update = CaseBlock(
            version=V2,
            case_id=self.case._id,
            user_id=user_id or 'FIXME',
            update=dict((k, convert_prop(getattr(self, k))) for k in props)
        ).as_xml()
        # convert xml.etree to lxml
        case_update = etree.fromstring(legacy_etree.ElementTree.tostring(case_update))

        return case_update
