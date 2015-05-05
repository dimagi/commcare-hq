from tastypie import fields
from corehq.apps.locations.models import Location, root_locations
from corehq.apps.locations.permissions import (user_can_edit_location,
                                               user_can_view_location)
from corehq.apps.api.resources.v0_1 import CustomResourceMeta, LoginAndDomainAuthentication
from corehq.apps.api.util import get_object_or_not_exist
import json
from corehq.apps.api.resources import HqBaseResource


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
        
        if project.location_restriction_for_users:
            if parent_id:
                parent = get_object_or_not_exist(Location, parent_id, domain)
                return [child for child in
                        parent.sql_location.child_locations(include_archive_ancestors=include_inactive)
                        if user_can_view_location(user, child, project)]
            else:
                return [child for child in
                        root_locations(domain)
                        if user_can_view_location(user, child.sql_location, project)]
        elif parent_id:
            parent = get_object_or_not_exist(Location, parent_id, domain)
            return parent.sql_location.child_locations(include_archive_ancestors=include_inactive)

        return root_locations(domain)

    def dehydrate_can_edit(self, bundle):
        return user_can_edit_location(bundle.request.couch_user, bundle.obj, bundle.request.project)

    class Meta(CustomResourceMeta):
        authentication = LoginAndDomainAuthentication()
        object_class = Location
        resource_name = 'location'
        limit = 0
