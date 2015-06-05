from dimagi.utils.couch.database import iter_bulk_delete
from couchdbkit.exceptions import BulkSaveError
from corehq.util.test_utils import unit_testing_only
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
    loc_ids = [
        loc['id'] for loc in
        Location.get_db().view('locations/by_name', reduce=False).all()
    ]
    try:
        iter_bulk_delete(Location.get_db(), loc_ids)
    except BulkSaveError:
        pass

    SQLLocation.objects.all().delete()
