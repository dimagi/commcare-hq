from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.models import *
from casexml.apps.case.models import CommCareCase
from corehq.apps.locations.models import Location
from corehq.apps.commtrack import stockreport
from dimagi.utils.couch.database import get_db
from corehq.apps.sms.api import send_sms_to_verified_number
from lxml import etree
import logging
from dimagi.utils.couch.loosechange import map_reduce
from dimagi.utils.parsing import json_format_datetime
from datetime import datetime

logger = logging.getLogger('commtrack.sms')

def handle(verified_contact, text):
    """top-level handler for incoming stock report messages"""
    domain = Domain.get_by_name(verified_contact.domain)
    if not domain.commtrack_enabled:
        return False

    try:
        data = StockReport(domain, verified_contact).parse(text.lower())
        if not data:
            return False
    except Exception, e:
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

class StockReport(object):
    """a helper object for parsing raw stock report texts"""

    def __init__(self, domain, v):
        self.domain = domain
        self.v = v
        self.C = CommtrackConfig.for_domain(domain.name)

    # TODO sms parsing could really use unit tests
    def parse(self, text, location=None):
        """take in a text and return the parsed stock transactions"""
        args = text.split()

        if args[0] in self.C.keywords():
            # single action sms
            # TODO: support single-action by product, as well as by action?
            action = self.C.keywords()[args[0]]
            args = args[1:]

            if not location:
                location = self.location_from_code(args[0])
                args = args[1:]
        
            _tx = self.single_action_transactions(action, args)

        elif self.C.multiaction_enabled and (self.C.multiaction_keyword is None or args[0] == self.C.multiaction_keyword.lower()):
            # multiple action sms
            if self.C.multiaction_keyword:
                args = args[1:]

            if not location:
                location = self.location_from_code(args[0])
                args = args[1:]

            _tx = self.multiple_action_transactions(args)

        else:
            # initial keyword not recognized; delegate to another handler
            return None

        tx = list(_tx)
        if not tx:
            raise RuntimeError('stock report doesn\'t have any transactions')

        return {
            'timestamp': datetime.utcnow(),
            'user': self.v.owner,
            'phone': self.v.phone_number,
            'location': location,
            'transactions': tx,
        }

    def single_action_transactions(self, action, args):
        # special case to handle immediate stock-out reports
        if action == 'stockout':
            if all(looks_like_prod_code(arg) for arg in args):
                for prod_code in args:
                    yield mk_tx(self.product_from_code(prod_code), action, 0)
                return
            else:
                raise RuntimeError('can\'t include a quantity for stock-out action')
            
        grouping_allowed = (action == 'stockedoutfor')

        products = []
        for arg in args:
            if looks_like_prod_code(arg):
                products.append(self.product_from_code(arg))
            else:
                if not products:
                    raise RuntimeError('quantity "%s" doesn\'t have a product' % arg)
                if len(products) > 1 and not grouping_allowed:
                    raise RuntimeError('missing quantity for product "%s"' % products[-1].code)

                try:
                    value = int(arg)
                except:
                    raise RuntimeError('could not understand product quantity "%s"' % arg)

                for p in products:
                    yield mk_tx(p, action, value)
                products = []
        if products:
            raise RuntimeError('missing quantity for product "%s"' % products[-1].code)

    def multiple_action_transactions(self, args):
        action = None
        action_code = None
        product = None

        _args = iter(args)
        def next():
            return _args.next()

        found_product_for_action = True
        while True:
            try:
                keyword = next()
            except StopIteration:
                if not found_product_for_action:
                    raise RuntimeError('product expected for action "%s"' % action_code)
                break

            try:
                old_action_code = action_code
                action, action_code = self.C.keywords(multi=True)[keyword], keyword
                if not found_product_for_action:
                    raise RuntimeError('product expected for action "%s"' % old_action_code)
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
                    raise RuntimeError('need to specify an action before product')
                elif action == 'stockout':
                    value = 0
                else:
                    try:
                        value = int(next())
                    except (ValueError, StopIteration):
                        raise RuntimeError('quantity expected for product "%s"' % product.code)

                yield mk_tx(product, action, value)
                continue

            raise RuntimeError('do not recognize keyword "%s"' % keyword)

            
    def location_from_code(self, loc_code):
        """return the supply point case referenced by loc_code"""
        loc_code = loc_code.lower()
        loc = get_db().view('commtrack/locations_by_code',
                            key=[self.domain.name, loc_code],
                            include_docs=True).first()
        if loc is None:
            raise RuntimeError('invalid location code "%s"' % loc_code)
        return CommCareCase.get(loc['id'])

    def product_from_code(self, prod_code):
        """return the product doc referenced by prod_code"""
        prod_code = prod_code.lower()
        p = Product.get_by_code(self.domain.name, prod_code)
        if p is None:
            raise RuntimeError('invalid product code "%s"' % prod_code)
        return p

def mk_tx(product, action, value):
    return locals()

def looks_like_prod_code(code):
    try:
        int(code)
        return False
    except:
        return True

def product_subcases(supply_point):
    """given a supply point, return all the sub-cases for each product stocked at that supply point
    actually returns a mapping: product doc id => sub-case id
    """
    product_subcase_uuids = [ix.referenced_id for ix in supply_point.reverse_indices if ix.identifier == 'parent']
    product_subcases = CommCareCase.view('_all_docs', keys=product_subcase_uuids, include_docs=True)
    product_subcase_mapping = dict((subcase.dynamic_properties().get('product'), subcase._id) for subcase in product_subcases)
    return product_subcase_mapping

def to_instance(data):
    """convert the parsed sms stock report into an instance like what would be
    submitted from a commcare phone"""
    E = stockreport.XML()
    M = stockreport.XML(stockreport.META_XMLNS, 'jrm')

    product_subcase_mapping = product_subcases(data['location'])

    def mk_xml_tx(tx):
        tx['product_id'] = tx['product']._id
        tx['case_id'] = product_subcase_mapping[tx['product']._id]
        return stockreport.tx_to_xml(tx, E)

    deviceID = ''
    if data.get('phone'):
        deviceID = 'sms:%s' % data['phone']
    timestamp = json_format_datetime(data['timestamp'])

    root = E.stock_report(
        M.meta(
            M.userID(data['user']._id),
            M.deviceID(deviceID),
            M.timeStart(timestamp),
            M.timeEnd(timestamp)
        ),
        E.location(data['location']._id),
        *(mk_xml_tx(tx) for tx in data['transactions'])
    )

    return etree.tostring(root, encoding='utf-8', pretty_print=True)

def truncate(text, maxlen, ellipsis='...'):
    if len(text) > maxlen:
        return text[:maxlen-len(ellipsis)] + ellipsis
    else:
        return text

def send_confirmation(v, data):
    C = CommtrackConfig.for_domain(v.domain)

    location_name = Location.get(data['location'].location_[-1]).name

    action_to_code = dict((v, k) for k, v in C.keywords().iteritems())
    tx_by_action = map_reduce(lambda tx: [(tx['action'],)], data=data['transactions'], include_docs=True)
    def summarize_action(action, txs):
        def fragment(tx):
            quantity = tx['value'] if tx['value'] is not None else ''
            return '%s%s' % (tx['product'].code.lower(), quantity)
        return '%s %s' % (action_to_code[action].upper(), ' '.join(sorted(fragment(tx) for tx in txs)))

    msg = 'received stock report for %s(%s) %s' % (
        data['location'].site_code,
        truncate(location_name, 20),
        ' '.join(sorted(summarize_action(a, txs) for a, txs in tx_by_action.iteritems()))
    )

    send_sms_to_verified_number(v, msg)
