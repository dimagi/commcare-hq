from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import CaseBlock
from casexml.apps.case.xml import V2
from lxml import etree
from lxml.builder import ElementMaker
from datetime import datetime, date, timedelta
from receiver.util import spoof_submission
from corehq.apps.receiverwrapper.util import get_submit_url
from corehq.apps.commtrack.models import *
from dimagi.utils.couch.loosechange import map_reduce
import logging

logger = logging.getLogger('commtrack.incoming')

XMLNS = 'http://openrosa.org/commtrack/stock_report'
def _(tag, ns=XMLNS):
    return '{%s}%s' % (ns, tag)
def XML(ns=XMLNS):
    return ElementMaker(namespace=ns)

def process(domain, instance):
    """process an incoming commtrack stock report instance"""
    config = CommtrackConfig.for_domain(domain)
    root = etree.fromstring(instance)
    transactions = unpack_transactions(root, config)

    case_ids = [tx['case_id'] for tx in transactions]
    cases = dict((c._id, c) for c in CommCareCase.view('_all_docs', keys=case_ids, include_docs=True))

    # ensure transaction types are processed in the correct order
    def transaction_order(tx):
        return [action.action_name for action in config.actions].index(tx['action'])
    transactions.sort(key=transaction_order)
    # apply all transactions to each product case in bulk
    transactions_by_product = map_reduce(lambda tx: [(tx['case_id'],)], data=transactions, include_docs=True)

    for product_id, txs in transactions_by_product.iteritems():
        product_case = cases[product_id]
        case_block, reconciliations = process_product_transactions(product_case, txs)
        for recon in reconciliations:
            root.append(recon)
        root.append(case_block)

    submission = etree.tostring(root)
    logger.debug('submitting: %s' % submission)
    spoof_submission(get_submit_url(domain), submission)

# TODO: make a transaction class

# TODO: tag all transactions with 'order in which processed' info -- especially
# needed for the reconciliation transactions

def tx_from_xml(tx, config):
    data = {
        'product_id': tx.find(_('product')).text,
        'case_id': tx.find(_('product_entry')).text,
        'action': tx.find(_('action')).text,
        'value': int(tx.find(_('value')).text),
        'inferred': tx.attrib.get('inferred') == 'true',
    }
    data['base_action'] = config.actions_by_name[data['action']].action_type
    return data

def tx_to_xml(tx, E=None):
    if not E:
        E = XML()
        
    attr = {}
    if tx.get('inferred'):
        attr['inferred'] = 'true'
    return E.transaction(
        E.product(tx['product_id']),
        E.product_entry(tx['case_id']),
        E.action(tx['action']),
        E.value(str(tx['value'])),
        **attr
    )

def unpack_transactions(root, config):
    return [tx_from_xml(tx, config) for tx in root.findall(_('transaction'))]

def process_product_transactions(case, txs):
    """process all the transactions from a stock report for an individual
    product. we have to apply them in bulk because each one may update
    the case state that the next one works off of. therefore we have to
    keep track of the updated case state ourselves
    """
    current_state = StockState(case)
    reconciliations = []
    for tx in txs:
        recon = current_state.update(tx['base_action'], tx['value'])
        if recon:
            reconciliations.append(tx_to_xml(recon))
    return current_state.to_case_block(), reconciliations

class StockState(object):
    def __init__(self, case):
        self.case = case
        props = case.dynamic_properties()
        self.current_stock = int(props.get('current_stock', 0)) # int
        self.stocked_out_since = props.get('stocked_out_since') # date
        # worry about consumption rates later
        
    def update(self, action, value):
        """given the current stock state for a product at a location, update
        with the incoming datapoint
        
        fancy business logic to reconcile stock reports lives HERE
        """
        reconciliation_transaction = None
        def mk_reconciliation(diff):
            return {
                'product_id': self.case.product,
                'case_id': self.case._id,
                'action': 'receipts' if diff > 0 else 'consumption',
                'value': abs(diff),
                'inferred': True,
            }

        if action == 'stockout' or (action == 'stockedoutfor' and value > 0):
            self.current_stock = 0
            days_stocked_out = (value - 1) if action == 'stockedoutfor' else 0
            self.stocked_out_since = date.today() - timedelta(days=days_stocked_out)
        else:

            if action in ('stockonhand', 'prevstockonhand'):
                if self.current_stock != value:
                    reconciliation_transaction = mk_reconciliation(value - self.current_stock)
                self.current_stock = value
            elif action == 'receipts':
                self.current_stock += value
            elif action == 'consumption':
                self.current_stock -= value

            # data normalization
            if self.current_stock > 0:
                self.stocked_out_since = None
            else:
                self.current_stock = 0 # handle if negative
                if not self.stocked_out_since: # handle if stocked out date already set
                    self.stocked_out_since = date.today()

        return reconciliation_transaction

    def to_case_block(self, user=None):
        def convert_prop(val):
            return str(val) if val is not None else ''

        props = ['current_stock', 'stocked_out_since']

        case_update = CaseBlock(
            version=V2,
            case_id=self.case._id,
            user_id=user or 'FIXME',
            update=dict((k, convert_prop(getattr(self, k))) for k in props)
        ).as_xml()
        # convert xml.etree to lxml
        from xml.etree import ElementTree
        case_update = etree.fromstring(ElementTree.tostring(case_update))

        return case_update


