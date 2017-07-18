import json

from corehq.apps.api.resources.auth import LoginAndDomainAuthentication
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.resources.v0_1 import LocationResource, get_location_or_not_exist
from corehq.util.quickcache import quickcache


@quickcache(['project.name', 'show_administrative'], timeout=10)
def _user_locations_ids(project, show_administrative):
    locations = SQLLocation.by_domain(project.name)
    if show_administrative == 'False':
        locations = locations.filter(location_type__administrative=True)
    # admins and users not assigned to a location can see and edit everything
    return locations.values_list('location_id', flat=True)


class EWSLocationResource(LocationResource):

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        project = getattr(bundle.request, 'project', self.domain_obj(domain))
        parent_id = bundle.request.GET.get('parent_id', None)
        include_inactive = json.loads(bundle.request.GET.get('include_inactive', 'false'))
        show_administrative = bundle.request.GET.get('show_administrative', False)
        viewable = _user_locations_ids(project, show_administrative)

        if not parent_id:
            locs = SQLLocation.root_locations(domain, include_inactive)
        else:
            parent = get_location_or_not_exist(parent_id, domain)
            locs = parent.sql_location.child_locations(include_inactive)

        return [child for child in locs if child.location_id in viewable]

    class Meta(LocationResource.Meta):
        authentication = LoginAndDomainAuthentication(allow_session_auth=True)
        resource_name = 'ews_location'
