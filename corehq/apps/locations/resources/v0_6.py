from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.users.models import HqPermissions

from corehq.apps.locations.resources import v0_5


class LocationResource(v0_5.LocationResource):
    resource_name = 'location'

    class Meta:
        queryset = SQLLocation.active_objects.all()
        detail_uri_name = 'location_id'
        authentication = RequirePermissionAuthentication(HqPermissions.edit_locations)
        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get', 'put']
        always_return_data = True
        include_resource_uri = False
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
        if bundle.obj.parent:
            bundle.data['parent_location_id'] = bundle.obj.parent.location_id
        else:
            bundle.data['parent_location_id'] = ''
        bundle.data['location_type_name'] = bundle.obj.location_type.name
        bundle.data['location_type_code'] = bundle.obj.location_type.code
        return bundle

    def _get_location_type(self, type_code):
        try:
            return LocationType.objects.get(
                code=type_code
            )
        except LocationType.DoesNotExist:
            raise Exception('Could not find location type with the given code.')

    def _get_parent_location(self, id):
        try:
            return SQLLocation.objects.get(location_id=id)
        except SQLLocation.DoesNotExist:
            raise Exception("Could not find parent location with the given ID.")
