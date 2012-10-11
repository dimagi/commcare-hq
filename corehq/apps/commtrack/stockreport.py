from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import CaseBlock
from casexml.apps.case.xml import V2
from lxml import etree
from datetime import datetime, date, timedelta
from receiver.util import spoof_submission
from corehq.apps.receiverwrapper.util import get_submit_url
from corehq.apps.commtrack.models import *

XMLNS = 'http://openrosa.org/commtrack/stock_report'
def _(tag, ns=XMLNS):
    return '{%s}%s' % (ns, tag)

def process(domain, instance):
    """process an incoming commtrack stock report instance"""
    root = etree.fromstring(instance)

    case_ids = [e.text for e in root.findall('.//%s' % _('product_entry'))]
    cases = dict((c._id, c) for c in CommCareCase.view('_all_docs', keys=case_ids, include_docs=True))

    # ensure transaction types are processed in the correct order
    transactions = sorted(root.findall(_('transaction')), key=transaction_order)

    for tx in transactions:
        case_id = tx.find(_('product_entry')).text
        tx_data = (
            tx.find(_('action')).text,
            int(tx.find(_('value')).text),
        )
        case_block = process_transaction(tx_data, cases[case_id])
        root.append(case_block)

    submission = etree.tostring(root)
    print 'submitting:', submission
    spoof_submission(get_submit_url(domain), submission)

def transaction_order(tx):
    action = tx.find(_('action')).text
    return ACTION_TYPES.index(action)

def process_transaction(tx, case):
    """process an individual stock datapoint (action + value) from a stock report

    * examine the new data
    * reconcile it with the current stock info
    * encode the necessary data updates as case-xml blocks and annotate the
      original instance
    * submit the annotated instance to HQ for processing
    """
    action, value = tx
    current_state = StockState(case)
    current_state.update(action, value)
    return current_state.to_case_block()

class StockState(object):
    def __init__(self, case):
        self.case = case
        props = case.dynamic_properties()
        self.current_stock = int(props.get('current_stock', 0)) # int
        self.stocked_out_since = props.get('stocked_out_since') # date
        # worry about consumption rates later
        
    # todo: create 'inferred' transactions here? i.e., consumption if soh and
    # receipts only are reported
    def update(self, action, value):
        """given the current stock state for a product at a location, update
        with the incoming datapoint
        
        fancy business logic to reconcile stock reports lives HERE
        """
        if action == 'stockout':
            self.current_stock = 0
            self.stocked_out_since = date.today() - timedelta(days=value)
        else:

            if action == 'stockonhand':
                self.current_stock = value
            elif action == 'receipts':
                self.current_stock += value
            elif action == 'consumption':
                self.current_stock -= value

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


