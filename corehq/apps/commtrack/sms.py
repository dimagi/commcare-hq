from django.conf import settings
from corehq.apps.commtrack.const import RequisitionActions
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack import const
from corehq.apps.sms.api import send_sms_to_verified_number
from lxml import etree
import logging
from dimagi.utils.couch.loosechange import map_reduce
from dimagi.utils.parsing import json_format_datetime
from datetime import datetime
from corehq.apps.commtrack.util import get_supply_point
from corehq.apps.commtrack.xmlutil import XML, _
from corehq.apps.commtrack.models import Product, CommtrackConfig, StockTransaction, CommTrackUser
from corehq.apps.receiverwrapper.util import get_submit_url
from receiver.util import spoof_submission
from dimagi.utils import parsing as dateparse

logger = logging.getLogger('commtrack.sms')

class SMSError(RuntimeError):
    pass

def handle(verified_contact, text, msg=None):
    """top-level handler for incoming stock report messages"""
    domain = Domain.get_by_name(verified_contact.domain)
    if not domain.commtrack_enabled:
        return False

    try:
        data = StockReportParser(domain, verified_contact).parse(text.lower())
        if not data:
            return False
    except Exception, e: # todo: should we only trap SMSErrors?
        if settings.UNIT_TESTING or settings.DEBUG:
            raise
        send_sms_to_verified_number(verified_contact, 'problem with stock report: %s' % str(e))
        return True

    process(domain.name, data)
    send_confirmation(verified_contact, data)
    return True

def process(domain, data):
    import pprint
    logger.debug(pprint.pformat(data))

    xmlroot = to_instance(data)

    submit_time = xmlroot.find('.//%s' % _('timeStart', const.META_XMLNS)).text
    submission = etree.tostring(xmlroot, encoding='utf-8', pretty_print=True)
    logger.debug(submission)

    # submit it
    spoof_submission(get_submit_url(domain), submission,
                     headers={'HTTP_X_SUBMIT_TIME': submit_time},
                     hqsubmission=False)

class StockReportParser(object):
    """a helper object for parsing raw stock report texts"""

    def __init__(self, domain, v):
        self.domain = domain
        self.v = v

        self.location = None
        u = v.owner
        if domain.commtrack_enabled:
            # currently only support one location on the UI
            linked_loc = CommTrackUser.wrap(u.to_json()).location
            if linked_loc:
                self.location = get_supply_point(self.domain.name, loc=linked_loc)

        self.C = domain.commtrack_settings

    # TODO sms parsing could really use unit tests
    def parse(self, text):
        """take in a text and return the parsed stock transactions"""
        args = text.split()

        if len(args) == 0:
            # we'll allow blank messages to propagate further in case some
            # other handler cares about them.
            return None

        action_keyword = args[0]
        args = args[1:]
        if not self.location:
            if len(args) == 0:
                # todo: this will change when users are tied to locations
                # though need to make sure that PACK and APPROVE still require location code
                # (since they refer to locations different from the sender's loc)
                raise SMSError("must specify a location code")
            self.location = self.location_from_code(args[0])
            args = args[1:]

        action = self.C.action_by_keyword(action_keyword)
        if action and action.type == 'stock':
            # single action stock report
            # TODO: support single-action by product, as well as by action?
            _tx = self.single_action_transactions(action, args, self.transaction_factory(StockTransaction))

        elif action and action.type == 'req':
            # requisition
            if action.action in [RequisitionActions.APPROVAL, RequisitionActions.PACK]:
                _tx = self.requisition_bulk_action(action, args)
            else:
                _tx = self.single_action_transactions(action, args, self.transaction_factory(Requisition))

        # multiple action stock report
        elif self.C.multiaction_enabled and action_keyword == self.C.multiaction_keyword:
            _tx = self.multiple_action_transactions(args, self.transaction_factory(StockTransaction))

        else:
            # initial keyword not recognized; delegate to another handler
            return None

        tx = list(_tx)
        if not tx:
            raise SMSError("stock report doesn't have any transactions")

        return {
            'timestamp': datetime.utcnow(),
            'user': self.v.owner,
            'phone': self.v.phone_number,
            'location': self.location['location'],
            'transactions': tx,
        }

    def single_action_transactions(self, action, args, make_tx):
        # special case to handle immediate stock-out reports
        if action.action == const.StockActions.STOCKOUT:
            if all(looks_like_prod_code(arg) for arg in args):
                for prod_code in args:
                    yield make_tx(
                        product=self.product_from_code(prod_code),
                        action_def=action,
                        quantity=0,
                    )

                return
            else:
                raise SMSError("can't include a quantity for stock-out action")

        products = []
        for arg in args:
            if looks_like_prod_code(arg):
                products.append(self.product_from_code(arg))
            else:
                if not products:
                    raise SMSError('quantity "%s" doesn\'t have a product' % arg)
                if len(products) > 1:
                    raise SMSError('missing quantity for product "%s"' % products[-1].code)

                try:
                    value = int(arg)
                except:
                    raise SMSError('could not understand product quantity "%s"' % arg)

                for p in products:
                    yield make_tx(product=p, action_def=action, quantity=value)
                products = []
        if products:
            raise SMSError('missing quantity for product "%s"' % products[-1].code)

    def multiple_action_transactions(self, args, make_tx):
        action = None
        product = None

        # TODO: catch that we don't mix in requisiton and stock report keywords in the same multi-action message?

        _args = iter(args)
        def next():
            return _args.next()

        found_product_for_action = True
        while True:
            try:
                keyword = next()
            except StopIteration:
                if not found_product_for_action:
                    raise SMSError('product expected for action "%s"' % action_code)
                break

            old_action = action
            _next_action = self.C.action_by_keyword(keyword)
            if _next_action:
                action = _next_action
                if not found_product_for_action:
                    raise SMSError('product expected for action "%s"' % old_action.keyword)
                found_product_for_action = False
                continue

            try:
                product = self.product_from_code(keyword)
                found_product_for_action = True
            except:
                product = None
            if product:
                if not action:
                    raise SMSError('need to specify an action before product')
                elif action.action == const.StockActions.STOCKOUT:
                    value = 0
                else:
                    try:
                        value = int(next())
                    except (ValueError, StopIteration):
                        raise SMSError('quantity expected for product "%s"' % product.code)

                yield make_tx(product=product, action_def=action, quantity=value)
                continue

            raise SMSError('do not recognize keyword "%s"' % keyword)

    def requisition_bulk_action(self, action, args):
        if args:
            raise SMSError('extra arguments at end')

        yield stockreport.BulkRequisitionResponse(
            domain=self.domain,
            action_type=action.action_type,
            action_name=action.action_name,
            location_id=self.location.location_[-1],
        )

    def transaction_factory(self, baseclass):
        return lambda **kwargs: baseclass(
            domain=self.domain.name,
            location_id=self.location['location']._id,
            case_id=self.location['case']._id,
            **kwargs
        )

    def location_from_code(self, loc_code):
        """return the supply point case referenced by loc_code"""
        result = get_supply_point(self.domain.name, loc_code)
        if not result:
            raise SMSError('invalid location code "%s"' % loc_code)
        return result

    def product_from_code(self, prod_code):
        """return the product doc referenced by prod_code"""
        prod_code = prod_code.lower()
        p = Product.get_by_code(self.domain.name, prod_code)
        if p is None:
            raise SMSError('invalid product code "%s"' % prod_code)
        return p


def looks_like_prod_code(code):
    try:
        int(code)
        return False
    except:
        return True


def verify_transactions(transactions):
    """
    Make sure the transactions are all in a consistent state.
    Specifically, they all need to have the same case id.
    """
    assert transactions and all(
        tx.case_id == transactions[0].case_id for tx in transactions
    )


def convert_transactions_to_blocks(E, transactions):
    """
    Converts a list of StockTransactions (which in xml are entity items)
    to lists inside of balance or transfer blocks, depending on their types
    """

    balances = []
    transfers = []

    verify_transactions(transactions)

    for tx in transactions:
        if tx.action in (
            const.StockActions.STOCKONHAND, const.StockActions.STOCKOUT
        ):
            balances.append(tx)
        else:
            transfers.append(tx)

    stock_blocks = []

    if balances:
        attr = {
            'section-id': 'stock',
            'entity-id': transactions[0].case_id
        }
        if transactions[0].date:
            attr['date'] = transactions[0].date

        stock_blocks.append(E.balance(
            attr,
            *[tx.to_xml() for tx in balances]
        ))

    if transfers:
        attr = {
            'section-id': 'stock',
            'entity-id': transactions[0].case_id
        }

        if transactions[0].action == const.StockActions.RECEIPTS:
            here, there = ('dest', 'src')
        else:
            here, there = ('src', 'dest')

        attr[here] = transactions[0].case_id
        # no 'there' for now
        if transactions[0].subaction:
            attr['type'] = transactions[0].subaction

        stock_blocks.append(E.transfer(
            attr,
            *[tx.to_xml() for tx in transfers]
        ))

    return stock_blocks


def to_instance(data):
    """convert the parsed sms stock report into an instance like what would be
    submitted from a commcare phone"""
    E = XML()
    M = XML(const.META_XMLNS, 'jrm')

    deviceID = ''
    if data.get('phone'):
        deviceID = 'sms:%s' % data['phone']
    timestamp = json_format_datetime(data['timestamp'])

    transactions = data['transactions']
    category = set(tx.category for tx in transactions).pop()
    factory = {
        'stock': E.stock_report,
        'requisition': E.requisition,
    }[category]

    stock_blocks = convert_transactions_to_blocks(E, transactions)

    root = factory(
        M.meta(
            M.userID(data['user']._id),
            M.deviceID(deviceID),
            M.timeStart(timestamp),
            M.timeEnd(timestamp)
        ),
        E.location(data['location']._id),
        *stock_blocks
    )

    #TODO make sure all transaction types/case ids are the same

    return root

def truncate(text, maxlen, ellipsis='...'):
    if len(text) > maxlen:
        return text[:maxlen-len(ellipsis)] + ellipsis
    else:
        return text

def send_confirmation(v, data):
    C = CommtrackConfig.for_domain(v.domain)

    static_loc = data['location']
    location_name = static_loc.name

    tx_by_action = map_reduce(lambda tx: [(tx.action_config(C).name,)], data=data['transactions'], include_docs=True)
    def summarize_action(action, txs):
        return '%s %s' % (txs[0].action_config(C).keyword.upper(), ' '.join(sorted(tx.fragment() for tx in txs)))

    msg = 'received stock report for %s(%s) %s' % (
        static_loc.site_code,
        truncate(location_name, 20),
        ' '.join(sorted(summarize_action(a, txs) for a, txs in tx_by_action.iteritems()))
    )

    send_sms_to_verified_number(v, msg)
