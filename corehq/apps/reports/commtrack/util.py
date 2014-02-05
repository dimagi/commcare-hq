from corehq.apps.locations.models import all_locations


def supply_point_ids(locations):
    sp_ids = []
    for l in locations:
        if l.linked_supply_point():
            sp_ids.append(l.linked_supply_point()._id)
    return sp_ids


def get_relevant_supply_point_ids(domain, active_location=None):
    if active_location:
        return supply_point_ids([active_location] + active_location.descendants)
    else:
        return supply_point_ids(all_locations(domain))
