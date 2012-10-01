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

    frags = text.split()
    transactions = []

    def mk_transaction(product, action, value):
        return locals()
    def keyword_action_map(*args):
        """mapping of sms keywords back to the corresponding action"""
        master_map = dict(CS['keywords'])
        for map in args:
            master_map.update(map)
        return dict((v, k) for k, v in master_map.iteritems())

    if frags[0] in CS['keywords'].values():
        # single action sms
        action = keyword_action_map()[frags[0]]
        frags = frags[1:]

        if not location:
            location = location_from_code(frags[0])
            frags = frags[1:]
        
        def looks_like_prod_code(code):
            try:
                int(code)
                return False
            except:
                return True

        # special case to handle immediate stock-out reports
        special_case = False
        if action == 'stockout' and all(looks_like_prod_code(f) for f in frags):
            transactions.extend(mk_transaction(product_from_code(prod_code), action, 0) for prod_code in frags)
            special_case = True

        # normal parsing
        if not special_case:
            grouping_allowed = (action == 'stockout')

            products = []
            for f in frags:
                if looks_like_prod_code(f):
                    products.append(product_from_code(f))
                else:
                    value = int(f)
                    if not products:
                        raise RuntimeError('no product specified')
                    if len(products) > 1 and not grouping_allowed:
                        raise RuntimeError('missing a value')
                    for p in products:
                        transactions.append(mk_transaction(p, action, value))
                    products = []
            if products:
                raise RuntimeError('missing a value')

    elif CM and frags[0] == (CM['keyword'] or frags[0]):
        # multiple action sms
        if CM['keyword']:
            frags = frags[1:]
        action_map = keyword_action_map(CM.get('action_keywords', {}))

        if not location:
            location = location_from_code(frags[0])
            frags = frags[1:]

        for i in range(0, len(frags), 2):
            prod_code, keyword = frags[i].split(CM['delimeter'])
            value = int(frags[i + 1])

            product = product_from_code(prod_code)
            action = action_map[keyword]

            transactions.append(mk_transaction(product, action, value))

    return {
        'location': location,
        'transactions': transactions,
    }

def location_from_code(loc_code):
    # TODO fetch a real object
    return loc_code

def product_from_code(prod_code):
    # TODO fetch a real object
    return prod_code
