from tastypie import fields
from corehq import Domain
from corehq.apps.locations.models import Location, root_locations
from corehq.apps.api.resources.v0_1 import CustomResourceMeta, DomainAdminAuthentication
from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.api.resources import JsonResource
from corehq.apps.users.models import WebUser

class LocationResource(JsonResource):
    type = "location"
    uuid = fields.CharField(attribute='_id', readonly=True, unique=True)
    location_type = fields.CharField(attribute='location_type', readonly=True)
    name = fields.CharField(attribute='name', readonly=True, unique=True)

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        location_id = kwargs['pk']
        return get_object_or_not_exist(Location, location_id, domain)

    def obj_get_list(self, bundle, **kwargs):
        domain_name = kwargs['domain']
        parent_id = bundle.request.GET.get("parent_id", None)
        if parent_id:
            parent = get_object_or_not_exist(Location, parent_id, domain_name)
            user = WebUser.get_by_username(bundle.request.user.username)
            domain_object = Domain.get_by_name(domain_name)
            if user.get_domain_membership(domain_name).location_ids and domain_object.location_restriction_for_users:
                return parent.children_available_for_user(user, domain_name)
            else:
                return parent.children

        return root_locations(domain_name)

    class Meta(CustomResourceMeta):
        authentication = DomainAdminAuthentication()
        object_class = Location
        resource_name = 'location'
        limit = 0
