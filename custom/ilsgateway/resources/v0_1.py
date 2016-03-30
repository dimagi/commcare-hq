from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.locations.models import SQLLocation, Location
from corehq.apps.locations.resources.v0_1 import LocationResource, _user_locations_ids


class ILSLocationResource(LocationResource):

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        project = bundle.request.project
        parent_id = bundle.request.GET.get('parent_id', None)
        user = bundle.request.couch_user
        viewable = _user_locations_ids(user, project, only_editable=False)

        if not parent_id:
            locs = SQLLocation.root_locations(domain, include_archive_ancestors=False)
        else:
            parent = get_object_or_not_exist(Location, parent_id, domain)
            locs = parent.sql_location.get_children().filter(
                location_type__administrative=True,
                is_archived=False
            )
        return [child for child in locs if child.location_id in viewable]

    class Meta(LocationResource.Meta):
        resource_name = 'ils_location'
