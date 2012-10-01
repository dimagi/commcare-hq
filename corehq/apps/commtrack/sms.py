from corehq.apps.domain.models import Domain



def handle(v, text):
    domain = Domain.get_by_name(v.domain)
    if not domain.commtrack_enabled:
        return False

    # TODO error handling
    print parse_stock_report(text)

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

def parse_stock_report(text, location=None):
    CS = report_syntax_config['single_action']
    CM = report_syntax_config.get('multiple_action')

    def keyword_action_map(*args):
        """mapping of sms keywords back to the corresponding action"""
        master_map = dict(CS['keywords'])
        for map in args:
            master_map.update(map)
        return dict((v, k) for k, v in master_map.iteritems())

    args = text.split()

    if args[0] in CS['keywords'].values():
        # single action sms
        action = keyword_action_map()[args[0]]
        args = args[1:]

        if not location:
            location = location_from_code(args[0])
            args = args[1:]
        
        _tx = single_action_transactions(action, args)

    elif CM and args[0] == (CM['keyword'] or args[0]):
        # multiple action sms
        if CM['keyword']:
            args = args[1:]

        if not location:
            location = location_from_code(args[0])
            args = args[1:]

        action_map = keyword_action_map(CM.get('action_keywords', {}))
        _tx = multiple_action_transactions(CM, action_map, args)

    return {
        'location': location,
        'transactions': list(_tx),
    }


def single_action_transactions(action, args):
    # special case to handle immediate stock-out reports
    if action == 'stockout' and all(looks_like_prod_code(arg) for arg in args):
        for prod_code in args:
            yield mk_tx(product_from_code(prod_code), action, 0)
        return

    grouping_allowed = (action == 'stockout')

    products = []
    for arg in args:
        if looks_like_prod_code(arg):
            products.append(product_from_code(arg))
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

def multiple_action_transactions(C, action_map, args):
    for i in range(0, len(args), 2):
        prod_code, keyword = args[i].split(C['delimeter'])
        value = int(args[i + 1])

        product = product_from_code(prod_code)
        action = action_map[keyword]

        yield mk_tx(product, action, value)

def mk_tx(product, action, value):
    return locals()

def looks_like_prod_code(code):
    try:
        int(code)
        return False
    except:
        return True


def location_from_code(loc_code):
    # TODO fetch a real object
    return loc_code

def product_from_code(prod_code):
    # TODO fetch a real object
    return prod_code
