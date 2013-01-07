from dimagi.utils.couch.database import get_db


def all_supply_point_types(domain):
    return [e['key'][1] for e in get_db().view('commtrack/supply_point_types', startkey=[domain], endkey=[domain, {}], group_level=2)]
