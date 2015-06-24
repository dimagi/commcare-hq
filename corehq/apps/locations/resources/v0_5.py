from tastypie import fields
from tastypie.bundle import Bundle
from tastypie.constants import ALL
from tastypie.resources import ModelResource

from corehq.apps.api.resources import HqBaseResource
from corehq.apps.api.resources.v0_1 import DomainAdminAuthentication
from corehq.util.view_utils import absolute_reverse

from ..models import SQLLocation, LocationType


class SQLResourceURIMixin(object):
    def get_resource_uri(self, bundle_or_obj=None):
        if isinstance(bundle_or_obj, Bundle):
            obj = bundle_or_obj.obj
        elif bundle_or_obj is None:
            return None
        else:
            obj = bundle_or_obj

        return absolute_reverse('api_dispatch_detail', kwargs={
            'resource_name': self._meta.resource_name,
            'domain': obj.domain,
            'api_name': self._meta.api_name,
            'pk': obj.pk
        })


class LocationTypeResource(SQLResourceURIMixin, ModelResource, HqBaseResource):
    parent = fields.ForeignKey('self', 'parent_type', null=True)

    class Meta:
        resource_name = 'location_type'
        queryset = LocationType.objects.all()
        authentication = DomainAdminAuthentication()
        fields = [
            'id',
            'domain',
            'name',
            'code',
            'parent_type',
            'administrative',
            'view_descendants',
        ]
        filtering = {
            "domain": ('exact',),
        }


class LocationResource(SQLResourceURIMixin, ModelResource, HqBaseResource):
    location_data = fields.DictField('metadata')
    location_type = fields.ForeignKey(LocationTypeResource, 'location_type')
    parent = fields.ForeignKey('self', 'parent', null=True)

    class Meta:
        resource_name = 'location'
        queryset = SQLLocation.objects.filter(is_archived=False).all()
        authentication = DomainAdminAuthentication()
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
