import itertools
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2
from lxml import etree
from lxml.builder import ElementMaker
from xml import etree as legacy_etree
from datetime import date, timedelta
from corehq.apps.commtrack.const import RequisitionActions
from dimagi.utils.create_unique_filter import create_unique_filter
from dimagi.utils.decorators.memoized import memoized
from receiver.util import spoof_submission
from corehq.apps.receiverwrapper.util import get_submit_url
from dimagi.utils.couch.loosechange import map_reduce
import logging
from corehq.apps.commtrack.models import CommtrackConfig, RequisitionCase, SupplyPointProductCase
from corehq.apps.commtrack.requisitions import RequisitionState
from corehq.apps.commtrack import const

logger = logging.getLogger('commtrack.incoming')

XMLNS = const.COMMTRACK_REPORT_XMLNS
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
    user_id, transactions = unpack_transactions(root, config)
    transactions = list(normalize_transactions(transactions))

    def get_transactions(all_tx, type_filter):
        """get all the transactions of the relevant type (filtered by type_filter),
        grouped by product (returns a dict of 'product subcase id' => list of transactions),
        with each set of transactions sorted in the correct order for processing
        """
        return map_reduce(lambda tx: [(tx.case_id,)],
                          lambda v: sorted(v, key=lambda tx: tx.priority_order), # important!
                          data=filter(type_filter, all_tx),
                          include_docs=True)

    # split transactions by type and product
    stock_transactions = get_transactions(transactions, lambda tx: tx.category == 'stock')
    requisition_transactions = get_transactions(transactions, lambda tx: tx.category == 'requisition')

    case_ids = list(set(itertools.chain(*[tx.get_case_ids() for tx in transactions])))
    cases = dict((c._id, c) for c in CommCareCase.view('_all_docs', keys=case_ids, include_docs=True))

    # TODO: code to auto generate / update requisitions from transactions if
    # project is configured for that.

    # TODO: when we start receiving commcare-submitted reports, we should be using a server time rather
    # than relying on timeStart (however timeStart is set to server time for reports received via sms)
    submit_time = root.find('.//%s' % _('timeStart', META_XMLNS)).text
    post_processed_transactions = list(transactions)
    for product_id, product_case in cases.iteritems():
        stock_txs = stock_transactions.get(product_id, [])
        if stock_txs:
            case_block, reconciliations = process_product_transactions(user_id, submit_time, product_case, stock_txs)
            root.append(case_block)
            post_processed_transactions.extend(reconciliations)

        req_txs = requisition_transactions.get(product_id, [])
        if req_txs and config.requisitions_enabled:
            req = RequisitionState.from_transactions(user_id, product_case, req_txs)
            case_block = etree.fromstring(req.to_xml())
            root.append(case_block)
    replace_transactions(root, post_processed_transactions)

    submission = etree.tostring(root)
    logger.debug('submitting: %s' % submission)

    spoof_submission(get_submit_url(domain), submission,
                     headers={'HTTP_X_SUBMIT_TIME': submit_time},
                     hqsubmission=False)

class StockTransaction(object):
    def __init__(self, **kwargs):
        self.domain = kwargs.get('domain')
        self.location = kwargs.get('location')
        self.location_id = self.location.location_[-1] if self.location else None
        self.product = kwargs.get('product')
        self.product_id = kwargs.get('product_id') or self.product._id
        self.action_name = kwargs['action_name']
        self.value = kwargs['value']
        self.case_id = kwargs.get('case_id') or kwargs.get('get_caseid', lambda p: None)(self.product_id)
        self.inferred = kwargs.get('inferred', False)
        self.processing_order = kwargs.get('order')

        self.config = kwargs.get('config')
        if self.config:
            if not self.domain:
                self.domain = self.config.domain
            self.action_config = self.config.all_actions_by_name[self.action_name]
            self.priority_order = [action.action_name for action in self.config.all_actions()].index(self.action_name)

        assert self.product_id
        assert self.case_id

    def get_case_ids(self):
        # to standardize an API that could have one or more cases
        yield self.case_id

    @property
    def base_action_type(self):
        return self.action_config.action_type

    @classmethod
    def from_xml(cls, tx, config):
        data = {
            'product_id': tx.find(_('product')).text,
            'case_id': tx.find(_('product_entry')).text,
            'value': int(tx.find(_('value')).text),
            'inferred': tx.attrib.get('inferred') == 'true',
            'action_name': tx.find(_('action')).text,
        }
        return cls(config=config, **data)

    def to_xml(self, E=None, **kwargs):
        if not E:
            E = XML()

        attr = {}
        if self.inferred:
            attr['inferred'] = 'true'
        if self.processing_order is not None:
            attr['order'] = str(self.processing_order + 1)

        return E.transaction(
            E.product(self.product_id),
            E.product_entry(self.case_id),
            E.action(self.action_name),
            E.value(str(self.value)),
            **attr
        )

    @property
    def category(self):
        return 'stock'

    def fragment(self):
        """
        A short string representation of this to be used in sms correspondence
        """
        quantity = self.value if self.value is not None else ''
        return '%s%s' % (self.product.code.lower(), quantity)

    def __repr__(self):
        return '{action}: {value} (case: {case}, product: {product})'.format(
            action=self.action_name, value=self.value, case=self.case_id,
            product=self.product_id
        )

class Requisition(StockTransaction):
    @property
    def category(self):
        return 'requisition'

    @property
    @memoized
    def requisition_case_id(self):
        # for somewhat obscure reasons, the case_id is the id of the
        # supply_point_product case, so we add a new field for this.
        # though for newly created requisitions it's just empty
        if self.base_action_type == RequisitionActions.REQUEST:
            return None
        if self.base_action_type == RequisitionActions.RECEIPTS:
            # for receipts the id should point to the most recent open requisition
            # (or none)
            try:
                product_stock_case = SupplyPointProductCase.get(self.case_id)
                return RequisitionCase.open_for_product_case(
                    self.domain,
                    product_stock_case.location_[-1],
                    self.case_id
                )[0]
            except IndexError:
                # there was no open requisition. this is ok
                return None

        assert False, "%s is an unexpected action type!" % self.base_action_type

    @classmethod
    def from_xml(cls, tx, config):
        data = {
            'product_id': tx.find(_('product')).text,
            'case_id': tx.find(_('product_entry')).text,
            'value': int(tx.find(_('value')).text),
            'action_name': tx.find(_('action')).text,
        }
        return cls(config=config, **data)

    def to_xml(self, E=None, **kwargs):
        if not E:
            E = XML()

        return E.requisition(
            E.product(self.product_id),
            E.product_entry(self.case_id),
            E.value(str(self.value)),
            E.action(self.action_name)
        )

class RequisitionResponse(Requisition):

    @property
    def requisition_case_id(self):
        return self.case_id

class BulkRequisitionResponse(object):
    """
    A bulk response to a set of requisitions, for example "approve" or "pack".
    """
    # todo: it's possible this class should support explicit transactions/amounts
    # on a per-product basis, but won't until someone demands it

    def __init__(self, domain, action_type, action_name, location_id, config=None):
        self.domain = domain
        self.action_name = action_name
        self.action_type = action_type
        self.location_id = location_id
        self.case_id = None
        self.config = config


    @memoized
    def get_case_ids(self):
        # todo: too many couch requests
        for c in filter(create_unique_filter(lambda id: RequisitionCase.get(id).get_product_case_id()),
                        RequisitionCase.open_for_location(self.domain, self.location_id)):
            yield c

    def get_transactions(self):
        for case_id in self.get_case_ids():
            # this is going to hit the db a lot
            c = RequisitionCase.get(case_id)
            yield(RequisitionResponse(
                product_id = c.product_id,
                case_id=c._id,
                action_name=self.action_name,
                value=c.get_default_value(),
                inferred=True,
                config=self.config,
            ))


    @property
    def category(self):
        return 'requisition'

    @property
    def product_id(self):
        return const.ALL_PRODUCTS_TRANSACTION_TAG

    @classmethod
    def from_xml(cls, tx, config):
        data = {
            'domain': config.domain, # implicit assert that this isn't empty
            'action_name': tx.find(_('status')).text,
            'action_type': tx.find(_('status_type')).text,
            'location_id': tx.find(_('location')).text,
            'config': config,
        }
        return cls(**data)

    def to_xml(self, E=None, **kwargs):
        if not E:
            E = XML()

        return E.response(
            E.status(self.action_name),
            E.status_type(self.action_type),
            E.location(self.location_id),
            E.product(self.product_id),
        )

    def fragment(self):
        # for a bulk operation just indicate we touched everything
        return 'all'

    def __repr__(self):
        return 'bulk requisition response: %s' % self.action_name

def unpack_transactions(root, config):
    user_id = root.find('.//%s' % _('userID', META_XMLNS)).text
    def transactions():
        types = {
            'transaction': StockTransaction,
            'requisition': Requisition,
            'response': BulkRequisitionResponse,
        }
        for tag, factory in types.iteritems():
            for tx in root.findall(_(tag)):
                yield factory.from_xml(tx, config)

    return user_id, transactions()

def normalize_transactions(transactions):
    for t in transactions:
        if isinstance(t, BulkRequisitionResponse):
            # deal with the bulkness by creating individual transactions
            # for each relevant product
            for sub_t in t.get_transactions():
                yield sub_t
        else:
            yield t


def replace_transactions(root, new_tx):
    for tag in ('transaction', 'requisition', 'response'):
        for tx in root.findall(_(tag)):
            tx.getparent().remove(tx)
    for tx in new_tx:
        root.append(tx.to_xml())

def process_product_transactions(user_id, timestamp, case, txs):
    """process all the transactions from a stock report for an individual
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
        recon = current_state.update(tx.base_action_type, tx.value)
        if recon:
            set_order(recon)
            reconciliations.append(recon)
        set_order(tx)
    return current_state.to_case_block(user_id=user_id), reconciliations

class StockState(object):
    def __init__(self, case, reported_on):
        self.case = case
        self.last_reported = reported_on
        props = case.dynamic_properties()
        self.current_stock = int(props.get('current_stock') or 0)  # int
        self.stocked_out_since = props.get('stocked_out_since')  # date

    def update(self, action_type, value):
        """given the current stock state for a product at a location, update
        with the incoming datapoint
        
        fancy business logic to reconcile stock reports lives HERE
        """
        reconciliation_transaction = None
        def mk_reconciliation(diff):
            return StockTransaction(
                product_id=self.case.product,
                case_id=self.case._id,
                action_name='receipts' if diff > 0 else 'consumption', # TODO argh, these are base actions, not config actions
                value=abs(diff),
                inferred=True,
            )

        if action_type == 'stockout' or (action_type == 'stockedoutfor' and value > 0):
            if self.current_stock > 0:
                reconciliation_transaction = mk_reconciliation(-self.current_stock)

            self.current_stock = 0
            days_stocked_out = (value - 1) if action_type == 'stockedoutfor' else 0
            self.stocked_out_since = date.today() - timedelta(days=days_stocked_out)

        else:
            if action_type == 'stockonhand':
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
