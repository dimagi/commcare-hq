from django.core.exceptions import ObjectDoesNotExist
from tastypie import fields
from tastypie.resources import Resource
from corehq.apps.locations.models import Location, root_locations
from corehq.apps.api.resources.v0_1 import CustomResourceMeta
from corehq.apps.api.util import get_object_or_not_exist

class LocationResource(Resource):
    type = "location"
    uuid = fields.CharField(attribute='_id', readonly=True, unique=True)
    location_type = fields.CharField(attribute='location_type', readonly=True)
    name = fields.CharField(attribute='name', readonly=True, unique=True)

    def determine_format(self, request):
        return "application/json"

    def obj_get(self, request, **kwargs):
        domain = kwargs['domain']
        location_id = kwargs['pk']
        return get_object_or_not_exist(Location, location_id, domain)

    def obj_get_list(self, request, **kwargs):
        domain = kwargs['domain']
        parent_id = request.GET.get("parent_id", None)
        if parent_id:
            parent = get_object_or_not_exist(Location, parent_id, domain)
            return parent.children

        return root_locations(domain)

    class Meta(CustomResourceMeta):
        resource_name = 'location'
        limit = 0
