from corehq.apps.locations.models import all_locations
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.products.models import Product


def supply_point_ids(locations):
    keys = [[loc.domain, loc._id] for loc in locations]
    rows = SupplyPointCase.get_db().view(
        'commtrack/supply_point_by_loc',
        keys=keys,
        include_docs=False,
    )
    return [row['id'] for row in rows]


def get_relevant_supply_point_ids(domain, active_location=None):
    if active_location:
        return supply_point_ids([active_location] + active_location.descendants)
    else:
        return supply_point_ids(all_locations(domain))


def product_ids_filtered_by_program(domain, program):
    products = Product.by_program_id(domain, program, False)
    return [p['_id'] for p in products]
