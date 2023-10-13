from django.db.models import Max

from tastypie import fields as tp_f
from tastypie.exceptions import BadRequest, ImmediateHttpResponse, NotFound
from tastypie.http import HttpAccepted
from tastypie.resources import Resource

from corehq.apps.api.fields import UUIDField
from corehq.apps.api.resources import HqBaseResource
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.util import get_obj, object_does_not_exist
from corehq.apps.fixtures.exceptions import FixtureVersionError
from corehq.apps.fixtures.models import (
    Field,
    LookupTable,
    LookupTableRow,
    TypeField,
)
from corehq.apps.fixtures.utils import clear_fixture_cache
from corehq.apps.users.models import HqPermissions


def convert_fdt(fdi, type_cache=None):
    def get_tag(table_id):
        try:
            return LookupTable.objects.values("tag").get(id=table_id)["tag"]
        except LookupTable.DoesNotExist:
            return None

    if type_cache is None:
        tag = get_tag(fdi.table_id)
    else:
        try:
            tag = type_cache[fdi.table_id]
        except KeyError:
            tag = type_cache[fdi.table_id] = get_tag(fdi.table_id)
    if tag is None:
        return fdi
    fdi.fixture_type = tag
    return fdi


class FixtureResource(HqBaseResource):
    type = "fixture"
    fields = tp_f.DictField(attribute='fields', readonly=True, unique=True)
    # when null, that means the ref'd fixture type was not found
    fixture_type = tp_f.CharField(attribute='fixture_type', readonly=True,
                                  null=True)
    id = UUIDField(attribute='id', readonly=True, unique=True)

    def dehydrate_fields(self, bundle):
        try:
            return bundle.obj.fields_without_attributes
        except FixtureVersionError:
            return LookupTableItemResource.dehydrate_fields(None, bundle)

    def obj_get(self, bundle, **kwargs):
        return convert_fdt(get_sql_object_or_not_exist(
            LookupTableRow, kwargs['pk'], kwargs['domain']))

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        parent_id = bundle.request.GET.get("parent_id", None)
        parent_ref_name = bundle.request.GET.get("parent_ref_name", None)
        references = bundle.request.GET.get("references", None)
        child_type = bundle.request.GET.get("child_type", None)
        type_id = bundle.request.GET.get("fixture_type_id", None)
        type_tag = bundle.request.GET.get("fixture_type", None)

        if parent_id and parent_ref_name and child_type and references:
            parent_fdi = LookupTableRow.objects.get(id=parent_id)
            fdis = list(
                LookupTableRow.objects.with_value(
                    domain, child_type, parent_ref_name,
                    parent_fdi.fields_without_attributes[references])
            )
        elif type_id or type_tag:
            type_id = type_id or LookupTable.objects.by_domain_tag(domain, type_tag)
            fdis = list(LookupTableRow.objects.iter_rows(domain, table_id=type_id))
        else:
            fdis = list(LookupTableRow.objects.filter(domain=domain))

        type_cache = {}
        return [convert_fdt(fdi, type_cache) for fdi in fdis]

    def detail_uri_kwargs(self, bundle_or_obj):
        return {'pk': get_obj(bundle_or_obj).id.hex}

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(HqPermissions.edit_apps)
        object_class = LookupTableRow
        resource_name = 'fixture'
        limit = 0


class InternalFixtureResource(FixtureResource):

    # using the default resource dispatch function to bypass our authorization for internal use
    def dispatch(self, request_type, request, **kwargs):
        return Resource.dispatch(self, request_type, request, **kwargs)

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(HqPermissions.edit_apps, allow_session_auth=True)
        object_class = LookupTableRow
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

        query.delete()
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


class FieldsDictField(tp_f.DictField):
    # NOTE LookupTableItemResource.hydrate_fields() does not work
    # because whatever value it sets on bundle.obj is subquently
    # overwritten by the result of ApiField.hydrate().

    def hydrate(self, bundle):
        def make_field(data):
            if "field_value" in data:
                data = data.copy()
                data["value"] = data.pop("field_value")
            return Field(**data)

        if self.instance_name not in bundle.data:
            return super().hydrate(bundle)
        return {
            name: [make_field(f) for f in items["field_list"]]
            for name, items in bundle.data[self.instance_name].items()
        }


class LookupTableItemResource(HqBaseResource):
    id = UUIDField(attribute='id', readonly=True, unique=True)
    data_type_id = UUIDField(attribute='table_id')
    fields = FieldsDictField(attribute='fields')
    item_attributes = tp_f.DictField(attribute='item_attributes')

    # It appears that sort_key is not included in any user facing UI. It is only defined as
    # the order of rows in the excel file when uploaded. We'll keep this behavior by incrementing
    # the sort key on new item creations
    sort_key = tp_f.IntegerField(attribute='sort_key')

    def dehydrate_fields(self, bundle):
        def field_json(values):
            return {"field_list": [
                {"field_value": field.value, "properties": field.properties}
                for field in values
            ]}
        return {
            field_name: field_json(field_list)
            for field_name, field_list in bundle.obj.fields.items()
        }

    def obj_get(self, bundle, **kwargs):
        return get_sql_object_or_not_exist(LookupTableRow, kwargs['pk'], kwargs['domain'])

    def obj_get_list(self, bundle, domain, **kwargs):
        return list(LookupTableRow.objects.filter(domain=domain))

    def obj_delete(self, bundle, **kwargs):
        try:
            row = LookupTableRow.objects.get(id=kwargs['pk'])
        except LookupTableRow.DoesNotExist:
            raise NotFound('Lookup table item not found')
        row.delete()
        clear_fixture_cache(row.domain)
        return ImmediateHttpResponse(response=HttpAccepted())

    def obj_create(self, bundle, request=None, **kwargs):
        data_type_id = bundle.data.get('data_type_id', None)

        if not data_type_id:
            raise BadRequest("data_type_id must be specified")

        if not LookupTable.objects.filter(id=data_type_id).exists():
            raise NotFound('Lookup table not found')

        self.full_hydrate(bundle)
        bundle.obj.domain = kwargs['domain']
        bundle.obj.sort_key = LookupTableRow.objects.filter(
            domain=kwargs['domain'], table_id=data_type_id
        ).aggregate(value=Max('sort_key') + 1)["value"] or 0
        try:
            bundle.obj.save()
        finally:
            clear_fixture_cache(kwargs['domain'])
        return bundle

    def obj_update(self, bundle, **kwargs):
        if 'data_type_id' not in bundle.data:
            raise BadRequest("data_type_id must be specified")

        try:
            bundle.obj = LookupTableRow.objects.get(id=kwargs['pk'])
        except LookupTableRow.DoesNotExist:
            raise NotFound('Lookup table item not found')

        if bundle.obj.domain != kwargs['domain']:
            raise NotFound('Lookup table item not found')

        bundle = self.full_hydrate(bundle)
        if 'fields' in bundle.data or 'item_attributes' in bundle.data:
            try:
                bundle.obj.save()
            finally:
                clear_fixture_cache(bundle.obj.domain)

        return bundle

    def detail_uri_kwargs(self, bundle_or_obj):
        return {'pk': get_obj(bundle_or_obj).id.hex}

    class Meta(CustomResourceMeta):
        object_class = LookupTableRow
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
