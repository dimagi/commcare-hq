from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import HqPermissions

from corehq.apps.locations.resources import v0_5


class LocationResource(v0_5.LocationResource):
    resource_name = 'location'

    class Meta:
        queryset = SQLLocation.objects.filter(is_archived=False).all()
        detail_uri_name = 'location_id'
        authentication = RequirePermissionAuthentication(HqPermissions.edit_locations)
        allowed_methods = ['get']
        fields = {
            'domain',
            'location_id',
            'name',
            'site_code',
            'last_modified',
            'latitude',
            'longitude',
            'location_data',
        }
        filtering = {
            "domain": ('exact',),
        }

    def dehydrate(self, bundle):
        del bundle.data['resource_uri']
        if bundle.obj.parent:
            bundle.data['parent_location_id'] = bundle.obj.parent.location_id
        else:
            bundle.data['parent_location_id'] = ''
        bundle.data['location_type_name'] = bundle.obj.location_type.name
        bundle.data['location_type_code'] = bundle.obj.location_type.code
        return bundle
