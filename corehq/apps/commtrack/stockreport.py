from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import CaseBlock
from casexml.apps.case.xml import V2
from lxml import etree
from lxml.builder import ElementMaker
from xml import etree as legacy_etree
from datetime import date, timedelta
from receiver.util import spoof_submission
from corehq.apps.receiverwrapper.util import get_submit_url
from dimagi.utils.couch.loosechange import map_reduce
import logging
from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.commtrack.requisitions import RequisitionState

logger = logging.getLogger('commtrack.incoming')

XMLNS = 'http://openrosa.org/commtrack/stock_report'
META_XMLNS = 'http://openrosa.org/jr/xforms'
def _(tag, ns=XMLNS):
    return '{%s}%s' % (ns, tag)
def XML(ns=XMLNS, prefix=None):
    prefix_map = None
    if prefix:
        prefix_map = {prefix: ns}
    return ElementMaker(namespace=ns, nsmap=prefix_map)

def process(domain, instance):
    """process an incoming commtrack stock report instance"""
    config = CommtrackConfig.for_domain(domain)
    root = etree.fromstring(instance)
    transactions = unpack_transactions(root, config)

    case_ids = [tx.case_id for tx in transactions]
    cases = dict((c._id, c) for c in CommCareCase.view('_all_docs', keys=case_ids, include_docs=True))

    # ensure transaction types are processed in the correct order
    transactions.sort(key=lambda t: t.order)
    stock_transactions = [t for t in transactions if t.is_stock]
    requisition_transactions = [t for t in transactions if t.is_requisition]

    # TODO: code to auto generate / update requisitions from transactions if
    # project is configured for that.

    # first apply all transactions to each product case in bulk
    stock_transactions_by_product = map_reduce(lambda tx: [(tx.case_id,)],
                                               data=stock_transactions,
                                               include_docs=True)
    requisition_transactions_by_product = map_reduce(lambda tx: [(tx.case_id,)],
                                                     data=requisition_transactions,
                                                     include_docs=True)

    for product_id, product_case in cases.iteritems():
        stock_txs = stock_transactions_by_product.get(product_id, [])
        case_block, reconciliations = process_product_transactions(product_case, stock_txs)
        for recon in reconciliations:
            root.append(recon)
        root.append(case_block)

        # do the same for the requisitions
        req_txs = requisition_transactions_by_product.get(product_id, [])
        req = RequisitionState.from_transactions(product_case, req_txs)
        case_block = etree.fromstring(req.to_xml())
        root.append(case_block)

    submission = etree.tostring(root)
    logger.debug('submitting: %s' % submission)

    submit_time = root.find('.//%s' % _('timeStart', META_XMLNS)).text
    spoof_submission(get_submit_url(domain), submission, headers={'HTTP_X_SUBMIT_TIME': submit_time})

class StockTransaction(object):
    def __init__(self, config, user_id, product_id, case_id, action_name, value, inferred):
        self.config = config
        self.user_id = user_id
        self.product_id = product_id
        self.case_id = case_id
        self.action_name = action_name
        self.value = value
        self.inferred = inferred
        self.action_config = self.config.all_actions_by_name[self.action_name]

        # used for sorting - the order this appears in the config
        self.order = [action.action_name for action in self.config.all_actions()].index(self.action_name)

    def __repr__(self):
        return '{action}: {value} (case: {case}, product: {product})'.format(
            action=self.action_name, value=self.value, case=self.case_id,
            product=self.product_id
        )

    @property
    def is_stock(self):
        return self.action_config.is_stock

    @property
    def is_requisition(self):
        return self.action_config.is_requisition

    @classmethod
    def from_xml(cls, tx, user_id, config):
        data = {
            'product_id': tx.find(_('product')).text,
            'case_id': tx.find(_('product_entry')).text,
            'value': int(tx.find(_('value')).text),
            'inferred': tx.attrib.get('inferred') == 'true',
            'action_name': tx.find(_('action')).text,
        }
        return StockTransaction(config=config, user_id= user_id, **data)

# TODO: tag all transactions with 'order in which processed' info -- especially
# needed for the reconciliation transactions

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
    user_id = root.find('.//%s' % _('userID', META_XMLNS)).text
    return [StockTransaction.from_xml(tx, user_id, config) for tx in root.findall(_('transaction'))]

def process_product_transactions(case, txs):
    """process all the transactions from a stock report for an individual
    product. we have to apply them in bulk because each one may update
    the case state that the next one works off of. therefore we have to
    keep track of the updated case state ourselves
    """
    current_state = StockState(case)
    reconciliations = []
    user_id = None
    for tx in txs:
        if user_id is None:
            user_id = tx.user_id
        else:
            assert user_id == tx.user_id # these should all be the same user

        recon = current_state.update(tx.action_config.action_type, tx.value)
        if recon:
            reconciliations.append(tx_to_xml(recon))
    return current_state.to_case_block(user_id=user_id), reconciliations

class StockState(object):
    def __init__(self, case):
        self.case = case
        props = case.dynamic_properties()
        self.current_stock = int(props.get('current_stock', 0)) # int
        self.stocked_out_since = props.get('stocked_out_since') # date
        # worry about consumption rates later

    def update(self, action_type, value):
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

        if action_type == 'stockout' or (action_type == 'stockedoutfor' and value > 0):
            self.current_stock = 0
            days_stocked_out = (value - 1) if action_type == 'stockedoutfor' else 0
            self.stocked_out_since = date.today() - timedelta(days=days_stocked_out)
        else:

            if action_type in ('stockonhand', 'prevstockonhand'):
                if self.current_stock != value:
                    reconciliation_transaction = mk_reconciliation(value - self.current_stock)
                self.current_stock = value
            elif action_type == 'receipts':
                self.current_stock += value
            elif action_type == 'consumption':
                self.current_stock -= value

            # data normalization
            if self.current_stock > 0:
                self.stocked_out_since = None
            else:
                self.current_stock = 0 # handle if negative
                if not self.stocked_out_since: # handle if stocked out date already set
                    self.stocked_out_since = date.today()

        return reconciliation_transaction

    def to_case_block(self, user_id=None):
        def convert_prop(val):
            return str(val) if val is not None else ''

        props = ['current_stock', 'stocked_out_since']

        case_update = CaseBlock(
            version=V2,
            case_id=self.case._id,
            user_id=user_id or 'FIXME',
            update=dict((k, convert_prop(getattr(self, k))) for k in props)
        ).as_xml()
        # convert xml.etree to lxml
        case_update = etree.fromstring(legacy_etree.ElementTree.tostring(case_update))

        return case_update


