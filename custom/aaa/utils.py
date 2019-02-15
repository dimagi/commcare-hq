from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.locations.models import LocationType, SQLLocation


def build_location_filters(location_id):
    try:
        location = SQLLocation.objects.get(location_id=location_id)
    except SQLLocation.DoesNotExist:
        return {'state_id': 'ALL'}

    location_ancestors = location.get_ancestors(include_self=True)

    filters = {
        "{}_id".format(ancestor.location_type.code): ancestor.location_id
        for ancestor in location_ancestors
    }

    location_type = location.location_type
    child_location_type = LocationType.objects.filter(domain=location_type.domain, parent_type=location_type)
    filters["{}_id".format(child_location_type.code)] = 'All'

    return filters
