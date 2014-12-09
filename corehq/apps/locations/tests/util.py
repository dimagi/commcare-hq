from corehq.apps.locations.models import Location

TEST_DOMAIN = 'locations-test'
TEST_LOCATION_TYPE = 'location'


def make_loc(code, name=None, domain=TEST_DOMAIN, type=TEST_LOCATION_TYPE, parent=None):
    name = name or code
    loc = Location(site_code=code, name=name, domain=domain, location_type=type, parent=parent)
    loc.save()
    return loc
