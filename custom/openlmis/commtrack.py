from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.locations.models import Location


def get_supply_point(domain, facility):
    # todo
    return None


def sync_facility_to_supply_point(domain, facility):
    supply_point = get_supply_point(domain, facility)
    facility_dict = {
        'domain': domain,
        'location_type': facility.type,
        'external_id': facility.code,
        'name': facility.name,
        'site_code': facility.code,  # todo: do they have a human readable code?
        'latitude': facility.latitude,
        'longitude': facility.longitude,
    }
    if supply_point is None:
        if facility.parent_id:
            # todo, deal with parentage
            # parent = get_location_by_external_id()
            # facility_dict['parent'] = parent
            pass

        facility_loc = Location(**facility_dict)
        facility_loc.save()
        return make_supply_point(domain, facility_loc)

    else:
        # currently impossible
        raise NotImplemented('updating existing supply points is not yet supported')
