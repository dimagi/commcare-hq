from corehq.apps.locations.models import SQLLocation
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
    """
    Return a list of supply point ids for the selected location
    and all of its descendants OR all supply point ids in the domain.
    """
    def filter_relevant(queryset):
        return queryset.filter(
            supply_point_id__isnull=False
        ).values_list(
            'supply_point_id',
            flat=True
        )

    if active_location:
        sql_location = active_location.sql_location
        supply_point_ids = []
        if sql_location.supply_point_id:
            supply_point_ids.append(sql_location.supply_point_id)
        supply_point_ids += list(
            filter_relevant(sql_location.get_descendants())
        )

        return supply_point_ids
    else:
        return filter_relevant(SQLLocation.objects.filter(domain=domain))


def product_ids_filtered_by_program(domain, program):
    products = Product.by_program_id(domain, program, False)
    return [p['_id'] for p in products]
