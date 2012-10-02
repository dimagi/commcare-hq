from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.models import Product


def handle(v, text):
    domain = Domain.get_by_name(v.domain)
    if not domain.commtrack_enabled:
        return False

    # TODO error handling
    print StockReport(domain, report_syntax_config).parse(text)

    # TODO: if message doesn't parse, don't handle it and fallback
    # to a catch-all error handler?
    return True


report_syntax_config = {
    'single_action': {
        'keywords': {
            'stockonhand': 'soh',
            'receipts': 'r',
            'consumption': 'c',
            'stockout': 'so',
        }
    },
    'multiple_action': {
        'keyword': 'psi', # if None, treat all other smses as multiple-action
        'delimeter': '.',
        'action_keywords': {
            # action types not listed default to their single-action keywords
            'stockonhand': 'st',
        }
    }
}

class StockReport(object):
    def __init__(self, domain, config): # config should probably be pulled from domain automatically?
        self.domain = domain
        self.CS = config['single_action']
        self.CM = config.get('multiple_action')

    def parse(self, text, location=None):
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
        if action == 'stockout' and all(looks_like_prod_code(arg) for arg in args):
            for prod_code in args:
                yield mk_tx(self.product_from_code(prod_code), action, 0)
            return
            
        grouping_allowed = (action == 'stockout')

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

        for i in range(0, len(args), 2):
            prod_code, keyword = args[i].split(self.CM['delimeter'])
            value = int(args[i + 1])

            product = self.product_from_code(prod_code)
            action = action_map[keyword]

            yield mk_tx(product, action, value)
            
    def location_from_code(self, loc_code):
        # TODO fetch a real object
        return loc_code

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


