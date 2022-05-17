from uuid import UUID

from couchdbkit import ResourceNotFound
from tastypie import fields as tp_f
from tastypie.exceptions import BadRequest, ImmediateHttpResponse, NotFound
from tastypie.http import HttpAccepted
from tastypie.resources import Resource

from dimagi.utils.couch.bulk import CouchTransaction

from corehq.apps.api.fields import UUIDField
from corehq.apps.api.resources import CouchResourceMixin, HqBaseResource
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.util import get_obj, get_object_or_not_exist, object_does_not_exist
from corehq.apps.fixtures.models import (
    FieldList,
    FixtureDataItem,
    LookupTable,
    TypeField,
)
from corehq.apps.fixtures.upload.run_upload import clear_fixture_quickcache
from corehq.apps.fixtures.utils import clear_fixture_cache
from corehq.apps.users.models import HqPermissions


def convert_fdt(fdi):
    try:
        fdt = LookupTable.objects.get(id=fdi.data_type_id)
        fdi.fixture_type = fdt.tag
        return fdi
    except LookupTable.DoesNotExist:
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
            type_id = type_id or LookupTable.objects.by_domain_tag(domain, type_tag)
            fdis = list(FixtureDataItem.by_data_type(domain, type_id))
        else:
            fdis = list(FixtureDataItem.by_domain(domain))

        return [convert_fdt(fdi) for fdi in fdis]

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(HqPermissions.edit_apps)
        object_class = FixtureDataItem
        resource_name = 'fixture'
        limit = 0


class InternalFixtureResource(FixtureResource):

    # using the default resource dispatch function to bypass our authorization for internal use
    def dispatch(self, request_type, request, **kwargs):
        return Resource.dispatch(self, request_type, request, **kwargs)

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(HqPermissions.edit_apps, allow_session_auth=True)
        object_class = FixtureDataItem
        resource_name = 'fixture_internal'
        limit = 0


class LookupTableResource(HqBaseResource):
    id = UUIDField(attribute='id', readonly=True, unique=True)
    is_global = tp_f.BooleanField(attribute='is_global')
    tag = tp_f.CharField(attribute='tag')
    fields = tp_f.ListField(attribute='fields')
    item_attributes = tp_f.ListField(attribute='item_attributes')

    def dehydrate_fields(self, bundle):
        return [
            {
                'field_name': field.field_name,
                'properties': field.properties,
            }
            for field in bundle.obj.fields
        ]

    def obj_get(self, bundle, **kwargs):
        return get_sql_object_or_not_exist(LookupTable, kwargs['pk'], kwargs['domain'])

    def obj_get_list(self, bundle, domain, **kwargs):
        return list(LookupTable.objects.by_domain(domain))

    def obj_delete(self, bundle, **kwargs):
        query = LookupTable.objects.filter(id=kwargs['pk'])
        if not query.exists():
            raise NotFound('Lookup table not found')

        data_type = LookupTable._migration_get_couch_model_class().get(UUID(kwargs['pk']).hex)
        try:
            query.delete()
            with CouchTransaction() as transaction:
                data_type.recursive_delete(transaction)
        finally:
            clear_fixture_quickcache(kwargs['domain'], [data_type])
            clear_fixture_cache(kwargs['domain'])
        return ImmediateHttpResponse(response=HttpAccepted())

    def obj_create(self, bundle, request=None, **kwargs):
        def adapt(field):
            if "name" not in field and "field_name" in field:
                field = field.copy()
                field["name"] = field.pop("field_name")
            return field

        tag = bundle.data.get("tag")
        if LookupTable.objects.domain_tag_exists(kwargs['domain'], tag):
            raise BadRequest(f"A lookup table with name {tag} already exists")

        data = dict(bundle.data)
        data["fields"] = [TypeField(**adapt(f)) for f in data.get('fields', [])]
        bundle.obj = LookupTable(domain=kwargs['domain'], **data)
        bundle.obj.save()
        return bundle

    def obj_update(self, bundle, **kwargs):
        if 'tag' not in bundle.data:
            raise BadRequest("tag must be specified")

        try:
            bundle.obj = LookupTable.objects.get(id=kwargs['pk'])
        except LookupTable.DoesNotExist:
            raise NotFound('Lookup table not found')

        if bundle.obj.domain != kwargs['domain']:
            raise NotFound('Lookup table not found')

        if bundle.obj.tag != bundle.data['tag']:
            raise BadRequest("Lookup table tag cannot be changed")

        save = False
        if 'is_global' in bundle.data:
            save = True
            bundle.obj.is_global = bundle.data['is_global']

        if 'fields' in bundle.data:
            save = True
            bundle.obj.fields = [TypeField(**f) for f in bundle.data['fields']]

        if 'item_attributes' in bundle.data:
            save = True
            bundle.obj.item_attributes = bundle.data['item_attributes']

        if save:
            bundle.obj.save()
        return bundle

    def detail_uri_kwargs(self, bundle_or_obj):
        return {'pk': get_obj(bundle_or_obj).id.hex}

    class Meta(CustomResourceMeta):
        object_class = LookupTable
        detail_allowed_methods = ['get', 'put', 'delete']
        list_allowed_methods = ['get', 'post']
        resource_name = 'lookup_table'


class LookupTableItemResource(CouchResourceMixin, HqBaseResource):
    id = tp_f.CharField(attribute='get_id', readonly=True, unique=True)
    data_type_id = tp_f.CharField(attribute='data_type_id')
    fields = tp_f.DictField(attribute='fields')
    item_attributes = tp_f.DictField(attribute='item_attributes')

    # It appears that sort_key is not included in any user facing UI. It is only defined as
    # the order of rows in the excel file when uploaded. We'll keep this behavior by incrementing
    # the sort key on new item creations
    sort_key = tp_f.IntegerField(attribute='sort_key')

    def dehydrate_fields(self, bundle):
        return {
            field_name: field_list.to_api_json()
            for field_name, field_list in bundle.obj.fields.items()
        }

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(FixtureDataItem, kwargs['pk'], kwargs['domain'])

    def obj_get_list(self, bundle, domain, **kwargs):
        return list(FixtureDataItem.by_domain(domain))

    def obj_delete(self, bundle, **kwargs):
        try:
            data_item = FixtureDataItem.get(kwargs['pk'])
        except ResourceNotFound:
            raise NotFound('Lookup table item not found')
        try:
            with CouchTransaction() as transaction:
                data_item.recursive_delete(transaction)
        finally:
            data_type = LookupTable._migration_get_couch_model_class().get(data_item.data_type_id)
            clear_fixture_quickcache(data_item.domain, [data_type])
            clear_fixture_cache(data_item.domain)
        return ImmediateHttpResponse(response=HttpAccepted())

    def obj_create(self, bundle, request=None, **kwargs):
        data_type_id = bundle.data.get('data_type_id', None)

        if not data_type_id:
            raise BadRequest("data_type_id must be specified")

        if not LookupTable.objects.filter(id=data_type_id).exists():
            raise NotFound('Lookup table not found')

        number_items = len(FixtureDataItem.by_data_type(kwargs['domain'], data_type_id))
        bundle.obj = FixtureDataItem(bundle.data)
        bundle.obj.domain = kwargs['domain']
        bundle.obj.sort_key = number_items + 1
        try:
            bundle.obj.save()
        finally:
            data_type = LookupTable._migration_get_couch_model_class().get(data_type_id)
            clear_fixture_quickcache(kwargs['domain'], [data_type])
            clear_fixture_cache(kwargs['domain'])
        return bundle

    def obj_update(self, bundle, **kwargs):
        if 'data_type_id' not in bundle.data:
            raise BadRequest("data_type_id must be specified")

        try:
            bundle.obj = FixtureDataItem.get(kwargs['pk'])
        except ResourceNotFound:
            raise NotFound('Lookup table item not found')

        if bundle.obj.domain != kwargs['domain']:
            raise NotFound('Lookup table item not found')

        save = False
        if 'fields' in bundle.data:
            save = True
            bundle.obj.fields = {
                field_name: FieldList.wrap(field_list)
                for field_name, field_list in bundle.data['fields'].items()
            }

        if 'item_attributes' in bundle.data:
            save = True
            bundle.obj.item_attributes = bundle.data['item_attributes']

        if save:
            try:
                bundle.obj.save()
            finally:
                data_item = bundle.obj
                data_type = LookupTable._migration_get_couch_model_class().get(data_item.data_type_id)
                clear_fixture_quickcache(data_item.domain, [data_type])
                clear_fixture_cache(data_item.domain)

        return bundle

    class Meta(CustomResourceMeta):
        object_class = FixtureDataItem
        detail_allowed_methods = ['get', 'put', 'delete']
        list_allowed_methods = ['get', 'post']
        resource_name = 'lookup_table_item'


def get_sql_object_or_not_exist(cls, obj_id, domain):
    """
    Given a Document class, id, and domain, get that object or raise
    an ObjectDoesNotExist exception if it's not found or doesn't belong
    to the domain.
    """
    try:
        obj = cls.objects.get(id=obj_id)
        if obj.domain == domain:
            return obj
    except cls.DoesNotExist:
        pass
    raise object_does_not_exist(cls.__name__, obj_id)
