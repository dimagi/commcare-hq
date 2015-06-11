from dimagi.utils.couch.database import iter_bulk_delete
from couchdbkit.exceptions import BulkSaveError
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
    to_delete = [(Location, 'locations/by_name'),
                 (SupplyPointCase, 'commtrack/supply_point_by_loc')]
    for model, view in to_delete:
        ids = [
            doc['id'] for doc in
            model.get_db().view(view, reduce=False).all()
        ]
        try:
            iter_bulk_delete(model.get_db(), ids)
        except BulkSaveError:
            pass

    SQLLocation.objects.all().delete()
