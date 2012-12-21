from django.core.exceptions import ObjectDoesNotExist
from tastypie import fields
from tastypie.resources import Resource
from corehq.apps.locations.models import Location, root_locations
from corehq.apps.api.resources.v0_1 import CustomResourceMeta

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
        loc = Location.get(location_id)
        # stupid "security"
        if loc and loc.domain == domain and loc.doc_type == 'Location':
            return loc
        else:
            raise ObjectDoesNotExist()

    def obj_get_list(self, request, **kwargs):
        domain = kwargs['domain']
        parent_id = request.GET.get("parent_id", None)
        if parent_id:
            parent = Location.get(parent_id)
            if parent and parent.domain == domain and parent.doc_type == 'Location':
                return parent.children
            else:
                raise ObjectDoesNotExist()
        
        return root_locations(domain)

    class Meta(CustomResourceMeta):
        resource_name = 'location'
        limit = 0
