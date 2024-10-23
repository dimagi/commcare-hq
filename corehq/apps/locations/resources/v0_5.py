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
    parent = fields.ForeignKey('self', 'parent_type', null=True)

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


class LocationResource(BaseLocationsResource):
    location_data = fields.DictField('metadata')
    location_type = fields.ForeignKey(LocationTypeResource, 'location_type')
    parent = fields.ForeignKey('self', 'parent', null=True)

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
