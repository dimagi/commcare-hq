from django.http import HttpResponseForbidden
from tastypie import fields
from tastypie.bundle import Bundle
from tastypie.constants import ALL
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.resources import ModelResource

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.api.resources import HqBaseResource
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.users.models import HqPermissions
from corehq.util.view_utils import absolute_reverse

from ..models import LocationType, SQLLocation


class BaseLocationsResource(ModelResource, HqBaseResource):
    def dispatch(self, request_type, request, **kwargs):
        if not domain_has_privilege(request.domain, privileges.LOCATIONS):
            raise ImmediateHttpResponse(HttpResponseForbidden())
        return super().dispatch(request_type, request, **kwargs)


class LocationTypeResource(BaseLocationsResource):
    id = fields.IntegerField(
        attribute='id',
        readonly=True,
        unique=True,
        help_text='Numeric identifier of the location type.',
    )
    domain = fields.CharField(
        attribute='domain',
        help_text='Domain (project space) that owns the location type.',
    )
    name = fields.CharField(
        attribute='name',
        help_text='Name of the location type.',
    )
    code = fields.CharField(
        attribute='code',
        null=True,
        help_text='Slug identifying the location type, used to filter '
                  'locations and in bulk data imports.',
    )
    parent = fields.ForeignKey(
        'self',
        'parent_type',
        null=True,
        help_text='URI of the parent location type, or null if this is '
                  'a root-level type.',
    )
    administrative = fields.BooleanField(
        attribute='administrative',
        help_text='Whether this is an administrative location type '
                  '(a fixed geographic boundary, e.g. state or '
                  'district) as opposed to an inventory-management '
                  'type (e.g. facility).',
    )
    shares_cases = fields.BooleanField(
        attribute='shares_cases',
        help_text='Whether users assigned to a location of this type '
                  'share cases owned by that location.',
    )
    view_descendants = fields.BooleanField(
        attribute='view_descendants',
        help_text='Whether users assigned to a location of this type '
                  'can view data belonging to descendant locations.',
    )

    class Docs:
        summary = 'Location Types'
        description = (
            'List the location types configured in a project space, or '
            'fetch a single location type by identifier. Location '
            'types define the organizational hierarchy (for example '
            'state, district, or facility) that locations belong to.'
        )
        field_schemas = {
        }

    class Meta(object):
        resource_name = 'location_type'
        queryset = LocationType.objects.all()
        authentication = RequirePermissionAuthentication(HqPermissions.edit_locations)
        fields = [
            'id',
            'domain',
            'name',
            'code',
            'parent_type',
            'administrative',
            'shares_cases',
            'view_descendants',
        ]
        filtering = {
            "domain": ('exact',),
        }
        # This resource implements no obj_create/obj_update/obj_delete,
        # and relies on the default ReadOnlyAuthorization, which rejects
        # any write with 401. Without these, Tastypie's own default
        # ``allowed_methods`` would still publish POST/PUT/PATCH/DELETE
        # as if they worked.
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_list'):
        if isinstance(bundle_or_obj, Bundle):
            obj = bundle_or_obj.obj
        elif bundle_or_obj is None:
            return super().get_resource_uri(bundle_or_obj, url_name)
        else:
            obj = bundle_or_obj

        return absolute_reverse('api_dispatch_detail', kwargs={
            'resource_name': self._meta.resource_name,
            'domain': obj.domain,
            'api_name': self.api_name,
            'pk': obj.pk
        })

    def dehydrate_parent(self, bundle):
        if bundle.obj.parent_type:
            return self.get_resource_uri(bundle.obj.parent_type)


class LocationResource(BaseLocationsResource):
    id = fields.IntegerField(
        attribute='id',
        readonly=True,
        unique=True,
        help_text='Numeric identifier of the location.',
    )
    name = fields.CharField(
        attribute='name',
        null=True,
        help_text='Name of the location.',
    )
    domain = fields.CharField(
        attribute='domain',
        help_text='Domain (project space) that owns the location.',
    )
    location_id = fields.CharField(
        attribute='location_id',
        unique=True,
        help_text='UUID of the location.',
    )
    site_code = fields.CharField(
        attribute='site_code',
        help_text='Unique (within the domain) code identifying the '
                  'location, used in case sharing and bulk data.',
    )
    external_id = fields.CharField(
        attribute='external_id',
        null=True,
        help_text='Identifier of the location in an external system, '
                  'if any.',
    )
    created_at = fields.DateTimeField(
        attribute='created_at',
        help_text='Date and time the location was created.',
    )
    last_modified = fields.DateTimeField(
        attribute='last_modified',
        help_text='Date and time the location was last modified.',
    )
    latitude = fields.DecimalField(
        attribute='latitude',
        null=True,
        help_text='Latitude coordinate of the location.',
    )
    longitude = fields.DecimalField(
        attribute='longitude',
        null=True,
        help_text='Longitude coordinate of the location.',
    )
    location_data = fields.DictField(
        'metadata',
        help_text='Custom data associated with the location, keyed by '
                  'field name.',
    )
    location_type = fields.ForeignKey(
        LocationTypeResource,
        'location_type',
        help_text='URI of the location type of this location.',
    )
    parent = fields.ForeignKey(
        'self',
        'parent',
        null=True,
        help_text='URI of the parent location, or null if this is a '
                  'root-level location.',
    )

    class Docs:
        summary = 'Locations'
        description = (
            'List locations in a project space, or fetch a single '
            'location by identifier. Locations represent the places, '
            'facilities or administrative areas where a project '
            'operates, arranged in a hierarchy of location types.'
        )
        examples = {'list_response': 'location/v1/list_response.json'}
        field_schemas = {
        }

    class Meta(object):
        resource_name = 'location'
        detail_uri_name = 'location_id'
        queryset = SQLLocation.objects.filter(is_archived=False).all()
        authentication = RequirePermissionAuthentication(HqPermissions.edit_locations)
        allowed_methods = ['get']
        fields = [
            'id',
            'name',
            'domain',
            'location_id',
            'site_code',
            'external_id',
            'created_at',
            'last_modified',
            'latitude',
            'longitude',
        ]
        filtering = {
            'domain': ['exact'],
            'site_code': ['exact'],
            'external_id': ['exact'],
            'created_at': ALL,
            'last_modified': ALL,
            'latitude': ALL,
            'longitude': ALL,
        }

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_list'):
        if isinstance(bundle_or_obj, Bundle):
            obj = bundle_or_obj.obj
        elif bundle_or_obj is None:
            return super().get_resource_uri(bundle_or_obj, url_name)
        else:
            obj = bundle_or_obj

        return absolute_reverse('api_dispatch_detail', kwargs={
            'resource_name': self._meta.resource_name,
            'domain': obj.domain,
            'api_name': self.api_name,
            'location_id': obj.location_id
        })

    def dehydrate_location_type(self, bundle):
        if bundle.obj.location_type_id:
            return absolute_reverse('api_dispatch_detail', kwargs={
                'resource_name': 'location_type',
                'domain': bundle.obj.domain,
                'api_name': self.api_name,
                'pk': bundle.obj.location_type_id,
            })

    def dehydrate_parent(self, bundle):
        if bundle.obj.parent:
            return self.get_resource_uri(bundle.obj.parent)
