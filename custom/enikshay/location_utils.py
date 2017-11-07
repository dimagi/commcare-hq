from __future__ import absolute_import
from collections import namedtuple

from custom.enikshay.exceptions import NikshayLocationNotFound, NikshayCodeNotFound


def get_health_establishment_hierarchy_codes(location):
    def get_parent(parent_type):
        parent = location.get_parent_of_type(parent_type)
        if not parent:
            raise NikshayLocationNotFound(
                "Missing parent of type {location_type} for {location_id}".format(
                    location_type=parent_type,
                    location_id=location.location_id))
        return parent[0]

    HealthEstablishmentHierarchy = namedtuple('HealthEstablishmentHierarchy', 'stcode dtcode')
    state = get_parent('sto')
    district = get_parent('dto')
    try:
        return HealthEstablishmentHierarchy(
            stcode=state.metadata['nikshay_code'],
            dtcode=district.metadata['nikshay_code'],
        )
    except (KeyError, AttributeError) as e:
        raise NikshayCodeNotFound("Nikshay codes not found: {}".format(e))
