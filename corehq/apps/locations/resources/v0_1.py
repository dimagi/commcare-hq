import json
from tastypie import fields

from corehq.apps.api.resources.v0_1 import CustomResourceMeta, LoginAndDomainAuthentication
from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.api.resources import HqBaseResource

from ..models import Location, root_locations
from ..permissions import editable_locations_ids, viewable_locations_ids


class LocationResource(HqBaseResource):
    type = "location"
    uuid = fields.CharField(attribute='location_id', readonly=True, unique=True)
    location_type = fields.CharField(attribute='location_type', readonly=True)
    is_archived = fields.BooleanField(attribute='is_archived', readonly=True)
    can_edit = fields.BooleanField(readonly=True)
    name = fields.CharField(attribute='name', readonly=True, unique=True)

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        location_id = kwargs['pk']
        return get_object_or_not_exist(Location, location_id, domain)

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        project = bundle.request.project
        parent_id = bundle.request.GET.get('parent_id', None)
        include_inactive = json.loads(bundle.request.GET.get('include_inactive', 'false'))
        user = bundle.request.couch_user
        viewable = viewable_locations_ids(user, project)

        if not parent_id:
            locs = root_locations(domain)
        else:
            parent = get_object_or_not_exist(Location, parent_id, domain)
            locs = parent.sql_location.child_locations(include_archive_ancestors=include_inactive)

        return [child for child in locs if child.location_id in viewable]

    def dehydrate_can_edit(self, bundle):
        return bundle.obj.location_id in editable_locations_ids(bundle.request.couch_user, bundle.request.project)

    class Meta(CustomResourceMeta):
        authentication = LoginAndDomainAuthentication()
        object_class = Location
        resource_name = 'location'
        limit = 0
