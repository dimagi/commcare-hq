from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit import ResourceNotFound
from tastypie import fields as tp_f
from tastypie.resources import Resource
from corehq.apps.api.resources import HqBaseResource, CouchResourceMixin
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.users.models import Permissions


def convert_fdt(fdi):
    try:
        fdt = FixtureDataType.get(fdi.data_type_id)
        fdi.fixture_type = fdt.tag
        return fdi
    except ResourceNotFound:
        return fdi


class FixtureResource(CouchResourceMixin, HqBaseResource):
    type = "fixture"
    fields = tp_f.DictField(attribute='try_fields_without_attributes',
                            readonly=True, unique=True)
    # when null, that means the ref'd fixture type was not found
    fixture_type = tp_f.CharField(attribute='fixture_type', readonly=True,
                                  null=True)
    id = tp_f.CharField(attribute='_id', readonly=True, unique=True)

    def obj_get(self, bundle, **kwargs):
        return convert_fdt(get_object_or_not_exist(
            FixtureDataItem, kwargs['pk'], kwargs['domain']))

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        parent_id = bundle.request.GET.get("parent_id", None)
        parent_ref_name = bundle.request.GET.get("parent_ref_name", None)
        references = bundle.request.GET.get("references", None)
        child_type = bundle.request.GET.get("child_type", None)
        type_id = bundle.request.GET.get("fixture_type_id", None)
        type_tag = bundle.request.GET.get("fixture_type", None)

        if parent_id and parent_ref_name and child_type and references:
            parent_fdi = FixtureDataItem.get(parent_id)
            fdis = list(
                FixtureDataItem.by_field_value(
                    domain, child_type, parent_ref_name,
                    parent_fdi.fields_without_attributes[references])
            )
        elif type_id or type_tag:
            type_id = type_id or FixtureDataType.by_domain_tag(
                domain, type_tag).one()
            fdis = list(FixtureDataItem.by_data_type(domain, type_id))
        else:
            fdis = list(FixtureDataItem.by_domain(domain))

        return [convert_fdt(fdi) for fdi in fdis] or []

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.edit_apps)
        object_class = FixtureDataItem
        resource_name = 'fixture'
        limit = 0


class InternalFixtureResource(FixtureResource):

    # using the default resource dispatch function to bypass our authorization for internal use
    def dispatch(self, request_type, request, **kwargs):
        return Resource.dispatch(self, request_type, request, **kwargs)

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.edit_apps, allow_session_auth=True)
        object_class = FixtureDataItem
        resource_name = 'fixture_internal'
        limit = 0


class LookupTableResource(CouchResourceMixin, HqBaseResource):
    id = tp_f.CharField(attribute='get_id', readonly=True, unique=True)
    is_global = tp_f.BooleanField(attribute='is_global')
    tag = tp_f.CharField(attribute='tag')
    fields = tp_f.ListField(attribute='fields')

    # Intentionally leaving out item_attributes until I can figure out what they are
    # item_attributes = tp_f.ListField(attribute='item_attributes')

    def dehydrate_fields(self, bundle):
        return [
            {
                'field_name': field.field_name,
                'properties': field.properties,
            }
            for field in bundle.obj.fields
        ]

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(FixtureDataType, kwargs['pk'], kwargs['domain'])

    def obj_get_list(self, bundle, domain, **kwargs):
        return list(FixtureDataType.by_domain(domain))

    class Meta(CustomResourceMeta):
        object_class = FixtureDataType
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'lookup_table'
