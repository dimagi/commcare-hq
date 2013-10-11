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


def supply_point_to_json(supply_point):
    base = {
        'agentCode': supply_point.location.site_code,
        'agentName': supply_point.name,
        'active': not supply_point.closed,
    }
    if supply_point.location.parent:
        base['parentFacilityCode'] = supply_point.location.parent.external_id

    # todo phone number
    return base


def sync_supply_point_to_openlmis(supply_point, openlmis_endpoint):
    """
    https://github.com/OpenLMIS/documents/blob/master/4.1-CreateVirtualFacility%20API.md
    {
        "agentCode":"A2",
        "agentName":"AgentVinod",
        "parentFacilityCode":"F10",
        "phoneNumber":"0099887766",
        "active":"true"
    }
    """
    return openlmis_endpoint.create_virtual_facility(supply_point_to_json(supply_point))
