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
