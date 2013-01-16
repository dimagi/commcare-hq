from dimagi.utils.couch.database import get_db
from corehq.apps.commtrack.models import *

def all_supply_point_types(domain):
    return [e['key'][1] for e in get_db().view('commtrack/supply_point_types', startkey=[domain], endkey=[domain, {}], group_level=2)]

def supply_point_type_categories(domain):
    config = CommtrackConfig.for_domain(domain)
    categories = config.supply_point_categories
    other_types = set(all_supply_point_types(domain)) - set(config.known_supply_point_types)
    categories['_oth'] = list(other_types)
    return categories

def make_product(domain, name, code):
    p = Product()
    p.domain = domain
    p.name = name
    p.code = code.lower()
    p.save()
    return p

def bootstrap_default(domain):
    c = CommtrackConfig(
        domain=domain,
        multiaction_enabled=True,
        multiaction_keyword='report',
        actions=[
            CommtrackActionConfig(
                action_type='receipts',
                keyword='r',
                caption='Received',
                name='received',
            ),
            CommtrackActionConfig(
                action_type='consumption',
                keyword='c',
                caption='Consumed',
                name='consumed',
            ),
            CommtrackActionConfig(
                action_type='stockonhand',
                keyword='soh',
                caption='Stock on hand',
                name='stock_on_hand',
            ),
            CommtrackActionConfig(
                action_type='stockout',
                keyword='so',
                caption='Stock-out',
                name='stock_out',
            ),
        ],
        supply_point_types=[],
    )
    c.save()

    make_product(domain, 'Sample Product 1', 'pp')
    make_product(domain, 'Sample Product 2', 'pq')
    make_product(domain, 'Sample Product 3', 'pr')

    return c
