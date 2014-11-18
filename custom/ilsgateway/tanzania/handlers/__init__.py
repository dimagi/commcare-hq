from corehq.apps.commtrack.util import get_supply_point


def get_location(domain, user, site_code):
    location = None
    if user and user.location:
        loc = user.location
        location = get_supply_point(domain, loc=loc)
    elif site_code:
        location = get_supply_point(domain, site_code=site_code)
    return location
