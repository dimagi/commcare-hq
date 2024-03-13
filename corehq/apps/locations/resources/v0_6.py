from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import HqPermissions

from corehq.apps.locations.forms import LocationForm
from corehq.apps.locations.resources import v0_5
from corehq.apps.locations.util import (
    validate_site_code, generate_site_code, has_siblings_with_name, get_location_type
)
from corehq.apps.locations.views import LocationFieldsView

from django.db.transaction import atomic
from django.utils.translation import gettext as _

from tastypie.exceptions import BadRequest


class LocationResource(v0_5.LocationResource):
    resource_name = 'location'
    patch_limit = 100

    class Meta:
        queryset = SQLLocation.active_objects.all()
        detail_uri_name = 'location_id'
        authentication = RequirePermissionAuthentication(HqPermissions.edit_locations)
        list_allowed_methods = ['get', 'post', 'patch']
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
        if 'name' not in bundle.data or 'location_type_code' not in bundle.data:
            raise BadRequest("'name' and 'location_type_code' are required fields when creating a new location.")
        bundle.obj = SQLLocation(domain=domain)
        self._update(bundle, domain, is_new_location=True)
        return bundle

    def obj_update(self, bundle, **kwargs):
        location_id = kwargs.get('location_id') or bundle.data.pop('location_id')
        try:
            bundle.obj = SQLLocation.objects.get(location_id=location_id, domain=kwargs['domain'])
        except SQLLocation.DoesNotExist:
            raise BadRequest(_("Could not update: could not find location with"
                               f" given ID {location_id} on the domain."))
        self._update(bundle, kwargs['domain'], is_new_location=False)
        return bundle

    def _update(self, bundle, domain, is_new_location=False):
        data = bundle.data
        if 'parent_location_id' in data:
            parent = self._get_parent_location(data.pop('parent_location_id'))
            if not is_new_location and 'location_type_code' not in data:
                # Otherwise validation of new parent will effectively be done under 'location_type_code'
                self._validate_new_parent(domain, bundle.obj, parent)
            bundle.obj.parent = parent
        if 'name' in data:
            self._validate_unique_among_siblings(bundle.obj, data['name'], bundle.obj.parent)
            bundle.obj.name = data.pop('name')
            if 'site_code' not in data:
                bundle.obj.site_code = generate_site_code(domain, bundle.obj.location_id, bundle.obj.name)
        if 'site_code' in data:
            site_code = validate_site_code(domain, bundle.obj.location_id, data.pop('site_code'), BadRequest)
            bundle.obj.site_code = site_code
        if 'location_data' in data:
            validator = LocationFieldsView.get_validator(domain)
            errors = validator(data['location_data'])
            if errors:
                raise BadRequest(errors)
            setattr(bundle.obj, 'metadata', data.pop('location_data'))
        if 'location_type_code' in data or is_new_location:
            bundle.obj.location_type = get_location_type(domain, bundle.obj, bundle.obj.parent,
                                                         data.pop('location_type_code', None),
                                                         BadRequest, is_new_location)
        if 'latitude' in data:
            bundle.obj.latitude = data.pop('latitude')
        if 'longitude' in data:
            bundle.obj.longitude = data.pop('longitude')

        if len(data):
            raise BadRequest(_(f"Invalid fields were included in request: {list(data.keys())}"))

        bundle.obj.save()

    def _get_parent_location(self, id):
        try:
            return SQLLocation.objects.get(location_id=id)
        except SQLLocation.DoesNotExist:
            raise Exception(_("Could not find parent location with the given ID."))

    def _validate_unique_among_siblings(self, location, name, parent):
        if has_siblings_with_name(location, name, parent.location_id):
            raise BadRequest(
                _("Location with same name and parent already exists.")
            )

    def _validate_new_parent(self, domain, location, parent):
        parent_allowed_types = LocationForm.get_allowed_types(domain, parent)
        if not parent_allowed_types:
            raise BadRequest(_("The selected parent location cannot have child locations!"))
        if location.location_type not in parent_allowed_types:
            raise BadRequest(_("Parent cannot have children of this location's type."))
        self._validate_unique_among_siblings(location, location.name, parent)

    @atomic
    def patch_list(self, request, **kwargs):
        def create_or_update(bundle, **kwargs):
            if 'location_id' in bundle.data:
                bundle = self.obj_update(bundle, **kwargs)
            else:
                bundle = self.obj_create(bundle, **kwargs)
            bundle.data['_id'] = bundle.obj.location_id  # For serialization
            return bundle
        return super().patch_list_replica(create_or_update, request, obj_limit=self.patch_limit, **kwargs)
