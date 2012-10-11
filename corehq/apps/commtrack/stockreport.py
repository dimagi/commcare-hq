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

XMLNS = 'http://openrosa.org/commtrack/stock_report'
def _(tag, ns=XMLNS):
    return '{%s}%s' % (ns, tag)
def XML(ns=XMLNS):
    return ElementMaker(namespace=ns)

def process(domain, instance):
    """process an incoming commtrack stock report instance"""
    root = etree.fromstring(instance)
    transactions = unpack_transactions(root)

    case_ids = [tx['case_id'] for tx in transactions]
    cases = dict((c._id, c) for c in CommCareCase.view('_all_docs', keys=case_ids, include_docs=True))

    # ensure transaction types are processed in the correct order
    transactions.sort(key=transaction_order)
    # apply all transactions to each product case in bulk
    transactions_by_product = map_reduce(lambda tx: [(tx['case_id'],)], data=transactions, include_docs=True)

    for product_id, txs in transactions_by_product.iteritems():
        product_case = cases[product_id]
        case_block = process_product_transactions(product_case, txs)
        root.append(case_block)

    submission = etree.tostring(root)
    print 'submitting:', submission
    spoof_submission(get_submit_url(domain), submission)

def tx_from_xml(tx):
    return {
        'case_id': tx.find(_('product_entry')).text,
        'action': tx.find(_('action')).text,
        'value': int(tx.find(_('value')).text),
    }

def tx_to_xml(tx, E=None):
    if not E:
        E = XML()
        
    return E.transaction(
        E.product_entry(tx['case_id']),
        E.action(tx['action']),
        E.value(str(tx['value']))
    )

def unpack_transactions(root):
    return [tx_from_xml(tx) for tx in root.findall(_('transaction'))]

def transaction_order(tx):
    return ACTION_TYPES.index(tx['action'])

def process_product_transactions(case, txs):
    """process all the transactions from a stock report for an individual
    product. we have to apply them in bulk because each one may update
    the case state that the next one works off of. therefore we have to
    keep track of the updated case state ourselves
    """
    current_state = StockState(case)
    for tx in txs:
        current_state.update(tx['action'], tx['value'])
    return current_state.to_case_block()

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
        if action in ('stockout', 'stockedoutfor'):
            self.current_stock = 0
            days_stocked_out = value if action == 'stockedoutfor' else 0
            self.stocked_out_since = date.today() - timedelta(days=days_stocked_out)
        else:

            if action in ('stockonhand', 'prevstockonhand'):
                self.current_stock = value
                # generate inferred transactions
                # TODO
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


