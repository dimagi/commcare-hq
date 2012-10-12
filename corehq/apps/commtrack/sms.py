from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.models import Product
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack import stockreport
from dimagi.utils.couch.database import get_db
from lxml import etree

def handle(v, text):
    """top-level handler for incoming stock report messages"""
    domain = Domain.get_by_name(v.domain)
    if not domain.commtrack_enabled:
        return False

    # TODO error handling
    data = StockReport(domain, report_syntax_config).parse(text)
    print data
    inst_xml = to_instance(v, data)
    print inst_xml
    
    stockreport.process(v.domain, inst_xml)

    # TODO: if message doesn't parse, don't handle it and fallback
    # to a catch-all error handler?
    return True

# todo, this will be pulled from domain somehow
report_syntax_config = {
    'single_action': {
        'keywords': { # only action types listed here are supported for this domain
            'prevstockonhand': 'soh',
            'receipts': 'r',
            'stockedoutfor': 'so',
        }
    },
    'multiple_action': {
        'keyword': 'psi', # if None, treat all other smses as multiple-action
        'delimeter': '.',
        'action_keywords': {
            # action types not listed default to their single-action keywords
            'prevstockonhand': 'st',
        }
    }
}

class StockReport(object):
    """a helper object for parsing raw stock report texts"""

    def __init__(self, domain, config): # config should probably be pulled from domain automatically?
        self.domain = domain
        self.CS = config['single_action']
        self.CM = config.get('multiple_action')

    def parse(self, text, location=None):
        """take in a text and return the parsed stock transactions"""
        args = text.split()

        if args[0] in self.CS['keywords'].values():
            # single action sms
            action = self.keyword_action_map()[args[0]]
            args = args[1:]

            if not location:
                location = self.location_from_code(args[0])
                args = args[1:]
        
            _tx = self.single_action_transactions(action, args)

        elif self.CM and args[0] == (self.CM['keyword'] or args[0]):
            # multiple action sms
            if self.CM['keyword']:
                args = args[1:]

            if not location:
                location = self.location_from_code(args[0])
                args = args[1:]

            _tx = self.multiple_action_transactions(args)

        return {
            'location': location,
            'transactions': list(_tx),
        }

    def keyword_action_map(self, *args):
        """mapping of sms keywords back to the corresponding action"""
        master_map = dict(self.CS['keywords'])
        for map in args:
            master_map.update(map)
        return dict((v, k) for k, v in master_map.iteritems())

    def single_action_transactions(self, action, args):
        # special case to handle immediate stock-out reports
        if action == 'stockout':
            if all(looks_like_prod_code(arg) for arg in args):
                for prod_code in args:
                    yield mk_tx(self.product_from_code(prod_code), action, 0)
                return
            else:
                raise RuntimeError('value not allowed')
            
        grouping_allowed = (action == 'stockedoutfor')

        products = []
        for arg in args:
            if looks_like_prod_code(arg):
                products.append(self.product_from_code(arg))
            else:
                if not products:
                    raise RuntimeError('no product specified')
                if len(products) > 1 and not grouping_allowed:
                    raise RuntimeError('missing a value')

                value = int(arg)
                for p in products:
                    yield mk_tx(p, action, value)
                products = []
        if products:
            raise RuntimeError('missing a value')

    def multiple_action_transactions(self, args):
        action_map = self.keyword_action_map(self.CM.get('action_keywords', {}))

        _args = iter(args)
        while True:
            try:
                op = _args.next()
            except StopIteration:
                # this is the only valid place for the arg list to end
                break

            prod_code, keyword = op.split(self.CM['delimeter'])
            product = self.product_from_code(prod_code)
            action = action_map[keyword]

            if action == 'stockout':
                value = 0
            else:
                value = int(_args.next())

            yield mk_tx(product, action, value)
            
    def location_from_code(self, loc_code):
        loc = get_db().view('commtrack/locations_by_code',
                            key=[self.domain.name, loc_code],
                            include_docs=True).first()
        if loc is None:
            raise RuntimeError('invalid location code')
        return CommCareCase.get(loc['id'])

    def product_from_code(self, prod_code):
        p = Product.get_by_code(self.domain.name, prod_code)
        if p is None:
            raise RuntimeError('invalid product code')
        return p

def mk_tx(product, action, value):
    return locals()

def looks_like_prod_code(code):
    try:
        int(code)
        return False
    except:
        return True


def to_instance(v, data):
    """convert the parsed sms stock report into an instance like what would be
    submitted from a commcare phone"""
    E = stockreport.XML()

    # find all stock product sub-cases linked to the supply point case, and build a mapping
    # of the general Product doc id to the site-specific product sub-case
    product_subcase_uuids = [ix.referenced_id for ix in data['location'].reverse_indices if ix.identifier == 'parent']
    product_subcases = CommCareCase.view('_all_docs', keys=product_subcase_uuids, include_docs=True)
    product_subcase_mapping = dict((subcase.dynamic_properties().get('product'), subcase._id) for subcase in product_subcases)

    def mk_xml_tx(tx):
        tx['case_id'] = product_subcase_mapping[tx['product']._id]
        return stockreport.tx_to_xml(tx, E)

    # TODO: add <meta>, user_id, etc.?
    root = E.stock_report(
        E.location(data['location']._id),
        *(mk_xml_tx(tx) for tx in data['transactions'])
    )

    return etree.tostring(root, encoding='utf-8', pretty_print=True)
