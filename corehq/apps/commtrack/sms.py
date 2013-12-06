from django.conf import settings
from corehq.apps.commtrack.const import RequisitionActions
from corehq.apps.domain.models import Domain
from casexml.apps.case.models import CommCareCase
from corehq.apps.locations.models import Location
from corehq.apps.commtrack import stockreport, const
from corehq.apps.sms.api import send_sms_to_verified_number
from lxml import etree
import logging
from dimagi.utils.couch.loosechange import map_reduce
from dimagi.utils.parsing import json_format_datetime
from datetime import datetime
from helpers import make_supply_point_product
from corehq.apps.commtrack.util import get_supply_point
from corehq.apps.commtrack.models import Product, CommtrackConfig, CommTrackUser

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
        if settings.UNIT_TESTING:
            raise
        send_sms_to_verified_number(verified_contact, 'problem with stock report: %s' % str(e))
        return True

    process(domain.name, data)
    send_confirmation(verified_contact, data)
    return True

def process(domain, data):
    logger.debug(data)
    inst_xml = to_instance(data)
    logger.debug(inst_xml)
    
    stockreport.process(domain, inst_xml)

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
                self.location = get_supply_point(self.domain.name, loc=linked_loc)['case']

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

        # single action stock report
        if action_keyword in self.C.stock_keywords():
            # TODO: support single-action by product, as well as by action?
            action_name = self.C.all_keywords()[action_keyword]
            action = self.C.all_actions_by_name[action_name]

            _tx = self.single_action_transactions(action, args, transaction_factory(self.location, stockreport.StockTransaction))

        # requisition
        elif action_keyword in self.C.requisition_keywords():
            action_name = self.C.all_keywords()[action_keyword]
            action = self.C.all_actions_by_name[action_name]

            if action.action_type in [RequisitionActions.APPROVAL, RequisitionActions.PACK]:
                _tx = self.requisition_bulk_action(action, args)
            else:
                _tx = self.single_action_transactions(action, args, transaction_factory(self.location, stockreport.Requisition))

        # multiple action stock report
        elif self.C.multiaction_enabled and action_keyword == self.C.multiaction_keyword.lower():
            _tx = self.multiple_action_transactions(args, transaction_factory(self.location, stockreport.StockTransaction))

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
            'location': self.location,
            'transactions': tx,
        }

    def single_action_transactions(self, action, args, make_tx):
        # special case to handle immediate stock-out reports
        if action.action_type == 'stockout':
            if all(looks_like_prod_code(arg) for arg in args):
                for prod_code in args:
                    yield make_tx(
                        domain=self.domain,
                        product=self.product_from_code(prod_code),
                        action_name=action.name,
                        value=0,
                    )

                return
            else:
                raise SMSError("can't include a quantity for stock-out action")

        grouping_allowed = (action.action_type == 'stockedoutfor')

        products = []
        for arg in args:
            if looks_like_prod_code(arg):
                products.append(self.product_from_code(arg))
            else:
                if not products:
                    raise SMSError('quantity "%s" doesn\'t have a product' % arg)
                if len(products) > 1 and not grouping_allowed:
                    raise SMSError('missing quantity for product "%s"' % products[-1].code)

                try:
                    value = int(arg)
                except:
                    raise SMSError('could not understand product quantity "%s"' % arg)

                for p in products:
                    yield make_tx(domain=self.domain, product=p, action_name=action.name, value=value)
                products = []
        if products:
            raise SMSError('missing quantity for product "%s"' % products[-1].code)

    def multiple_action_transactions(self, args, make_tx):
        action_name = None
        action_code = None
        product = None

        action_defs = self.C.all_actions_by_name

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

            try:
                old_action_code = action_code
                action_name, action_code = self.C.keywords(multi=True)[keyword], keyword
                action = action_defs.get(action_name)

                if not found_product_for_action:
                    raise SMSError('product expected for action "%s"' % old_action_code)
                found_product_for_action = False
                continue
            except KeyError:
                pass

            try:
                product = self.product_from_code(keyword)
                found_product_for_action = True
            except:
                product = None
            if product:
                if not action:
                    raise SMSError('need to specify an action before product')
                elif action.action_type == 'stockout':
                    value = 0
                else:
                    try:
                        value = int(next())
                    except (ValueError, StopIteration):
                        raise SMSError('quantity expected for product "%s"' % product.code)

                yield make_tx(product=product, action_name=action_name, value=value)
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

    def location_from_code(self, loc_code):
        """return the supply point case referenced by loc_code"""
        result = get_supply_point(self.domain.name, loc_code)['case']
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

def product_subcases(supply_point):
    """given a supply point, return all the sub-cases for each product stocked at that supply point
    actually returns a mapping: product doc id => sub-case id
    ACTUALLY returns a dict that will create non-existent product sub-cases on demand
    """
    product_subcase_uuids = [ix.referenced_id for ix in supply_point.reverse_indices if ix.identifier == const.PARENT_CASE_REF]
    product_subcases = CommCareCase.view('_all_docs', keys=product_subcase_uuids, include_docs=True)
    product_subcase_mapping = dict((subcase.dynamic_properties().get('product'), subcase._id) for subcase in product_subcases)

    def create_product_subcase(product_uuid):
        return make_supply_point_product(supply_point, product_uuid)._id

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

def transaction_factory(location, baseclass):
    """build the product->subcase mapping once and return a closure"""
    product_subcase_mapping = product_subcases(location)
    product_caseid = lambda product_id: product_subcase_mapping[product_id]
    return lambda **kwargs: baseclass(get_caseid=product_caseid,
                                      location=location,
                                      **kwargs)

def to_instance(data):
    """convert the parsed sms stock report into an instance like what would be
    submitted from a commcare phone"""
    E = stockreport.XML()
    M = stockreport.XML(stockreport.META_XMLNS, 'jrm')

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

    root = factory(
        M.meta(
            M.userID(data['user']._id),
            M.deviceID(deviceID),
            M.timeStart(timestamp),
            M.timeEnd(timestamp)
        ),
        E.location(data['location']._id),
        *[tx.to_xml() for tx in transactions]
    )

    return etree.tostring(root, encoding='utf-8', pretty_print=True)

def truncate(text, maxlen, ellipsis='...'):
    if len(text) > maxlen:
        return text[:maxlen-len(ellipsis)] + ellipsis
    else:
        return text

def send_confirmation(v, data):
    C = CommtrackConfig.for_domain(v.domain)

    static_loc = Location.get(data['location'].location_[-1])
    location_name = static_loc.name

    action_to_code = dict((v, k) for k, v in C.all_keywords().iteritems())
    tx_by_action = map_reduce(lambda tx: [(tx.action_name,)], data=data['transactions'], include_docs=True)
    def summarize_action(action, txs):
        return '%s %s' % (action_to_code[action].upper(), ' '.join(sorted(tx.fragment() for tx in txs)))

    msg = 'received stock report for %s(%s) %s' % (
        static_loc.site_code,
        truncate(location_name, 20),
        ' '.join(sorted(summarize_action(a, txs) for a, txs in tx_by_action.iteritems()))
    )

    send_sms_to_verified_number(v, msg)
