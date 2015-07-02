from dimagi.utils.couch.database import iter_bulk_delete
from corehq.util.test_utils import unit_testing_only
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import Location, SQLLocation

TEST_DOMAIN = 'locations-test'
TEST_LOCATION_TYPE = 'location'


def make_loc(code, name=None, domain=TEST_DOMAIN, type=TEST_LOCATION_TYPE, parent=None):
    name = name or code
    loc = Location(site_code=code, name=name, domain=domain, location_type=type, parent=parent)
    loc.save()
    return loc


@unit_testing_only
def delete_all_locations():
    ids = [
        doc['id'] for doc in
        SupplyPointCase.get_db().view('commtrack/supply_point_by_loc', reduce=False).all()
    ]
    iter_bulk_delete(SupplyPointCase.get_db(), ids)

    iter_bulk_delete(Location.get_db(), SQLLocation.objects.location_ids())

    SQLLocation.objects.all().delete()
