from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.users.models import HqPermissions

from corehq.apps.locations.resources import v0_5

from tastypie.exceptions import BadRequest, NotFound


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
        bundle.data['location_data'] = bundle.obj.metadata
        return bundle

    def obj_create(self, bundle, **kwargs):
        domain = kwargs['domain']
        if 'name' not in bundle.data:
            raise BadRequest("'name' is a required field.")
        if SQLLocation.objects.filter(domain=domain, site_code=bundle.data['site_code']).exists():
            raise BadRequest("Location on domain with site code already exists.")
        bundle.obj = SQLLocation(domain=domain)
        self._update(bundle)
        return bundle

    def obj_update(self, bundle, **kwargs):
        try:
            bundle.obj = SQLLocation.objects.get(location_id=kwargs['location_id'])
        except SQLLocation.DoesNotExist:
            raise BadRequest("Could not find location with given ID.")
        if bundle.obj.domain != kwargs.pop('domain'):
            raise NotFound('Location could not be found.')
        self._update(bundle)
        return bundle

    def _update(self, bundle):
        data = bundle.data
        # Invalid fields that might be common
        if data.pop('location_type_name', False):
            raise BadRequest('Location type name is not editable.')
        if data.pop('last_modified', False):
            raise BadRequest('\"last_modified\" field is not editable.')

        easy_field_names = ['name', 'site_code', 'latitude', 'longitude']
        for field_name in easy_field_names:
            if field_name in data:
                setattr(bundle.obj, field_name, data.pop(field_name))

        # Other, less "easy" fields
        if 'location_data' in data:
            for key, value in data['location_data'].items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise BadRequest("Location data keys and values must be strings.")
            setattr(bundle.obj, 'metadata', data.pop('location_data'))
        if 'location_type_code' in data:
            bundle.obj.location_type = self._get_location_type(data.pop('location_type_code'))
        if 'parent_location_id' in data:
            bundle.obj.parent = self._get_parent_location(data.pop('parent_location_id'))

        if len(data):
            raise BadRequest("Invalid fields were included in request.")

        bundle.obj.save()

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
