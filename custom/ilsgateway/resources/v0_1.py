from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.locations.models import SQLLocation, Location
from corehq.apps.locations.resources.v0_1 import LocationResource


class ILSLocationResource(LocationResource):

    def child_queryset(self, domain, include_inactive, parent_id):
        if not parent_id:
            locs = SQLLocation.root_locations(domain, include_archive_ancestors=False)
        else:
            parent = get_object_or_not_exist(Location, parent_id, domain)
            locs = parent.sql_location.get_children().filter(
                location_type__administrative=True,
                is_archived=False
            )
        return locs

    class Meta(LocationResource.Meta):
        resource_name = 'ils_location'
