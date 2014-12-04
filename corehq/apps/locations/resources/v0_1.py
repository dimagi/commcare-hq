from tastypie import fields
from corehq.apps.locations.models import Location, root_locations
from corehq.apps.api.resources.v0_1 import CustomResourceMeta, LoginAndDomainAuthentication
from corehq.apps.api.util import get_object_or_not_exist
import json
from corehq.apps.api.resources import HqBaseResource


class LocationResource(HqBaseResource):
    type = "location"
    uuid = fields.CharField(attribute='location_id', readonly=True, unique=True)
    location_type = fields.CharField(attribute='location_type', readonly=True)
    is_archived = fields.BooleanField(attribute='is_archived', readonly=True)
    name = fields.CharField(attribute='name', readonly=True, unique=True)

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        location_id = kwargs['pk']
        return get_object_or_not_exist(Location, location_id, domain)

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        parent_id = bundle.request.GET.get('parent_id', None)
        include_inactive = json.loads(bundle.request.GET.get('include_inactive', 'false'))
        if parent_id:
            parent = get_object_or_not_exist(Location, parent_id, domain)
            return parent.sql_location.child_locations(include_archive_ancestors=include_inactive)

        return root_locations(domain)

    class Meta(CustomResourceMeta):
        authentication = LoginAndDomainAuthentication()
        object_class = Location
        resource_name = 'location'
        limit = 0
