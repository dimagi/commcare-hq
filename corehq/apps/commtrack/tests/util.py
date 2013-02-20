from corehq.apps.locations.models import Location

TEST_DOMAIN = "commtrack-test"
TEST_LOCATION_TYPE = 'location'

def make_loc(name, domain=TEST_DOMAIN, type=TEST_LOCATION_TYPE):
    loc = Location(name=name, domain=domain, type=type)
    loc.save()
    return loc