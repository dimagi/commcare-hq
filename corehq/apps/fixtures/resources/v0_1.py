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
from corehq.util.validation import JSONSchemaValidator


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
        # This is a plain Resource with no obj_create/obj_update/
        # obj_delete, so a write raises NotImplementedError (500).
        # Without these, Tastypie's default ``allowed_methods`` would
        # still publish POST/PUT/PATCH/DELETE as if they worked.
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']


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
    """Lookup Table API resource

    Example ``fields`` format:

        "fields": [
            {
                "field_name": "tree",
                "properties": ["family"]
            }
        ]

    Example ``item_attributes`` format:

        "item_attributes": ["name", "height"]
    """
    id = UUIDField(
        attribute='id',
        readonly=True,
        unique=True,
        help_text='Unique identifier of the lookup table.',
    )
    is_global = tp_f.BooleanField(
        attribute='is_global',
        help_text='Whether the lookup table is accessible to all users '
                  'on the domain, regardless of location assignment. '
                  'Optional on create; defaults to false if omitted.',
    )
    tag = tp_f.CharField(
        attribute='tag',
        help_text='Name of the lookup table, unique within the domain. '
                  'Creating a table with a tag that already exists on '
                  'the domain is rejected. Required on every update '
                  'request, and cannot be changed to a different value.',
    )
    fields = tp_f.ListField(
        attribute='fields',
        help_text='The custom fields defined for rows of this lookup '
                  'table, each giving a field_name and the properties '
                  'available on it. Optional on create, defaulting to '
                  'an empty list. On update, if provided, this replaces '
                  'the entire list of fields.',
    )
    item_attributes = tp_f.ListField(
        attribute='item_attributes',
        help_text='Names of the item attributes available on rows of '
                  'this lookup table.',
    )

    validate_deserialized_data = JSONSchemaValidator({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "patternProperties": {
                        "^(field_)?name$": {"type": "string"},
                    },
                    "properties": {
                        "properties": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "additionalProperties": False,
                    "oneOf": [
                        {"not": {"required": ["field_name"]}},
                        {"not": {"required": ["name"]}},
                    ],
                },
            },
            "item_attributes": {"type": "array", "items": {"type": "string"}}
        },
    })

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
        try:
            query = LookupTable.objects.get(id=kwargs['pk'], domain=kwargs['domain'])
        except LookupTable.DoesNotExist:
            raise NotFound('Lookup table not found')

        query.delete()
        clear_fixture_cache(kwargs['domain'], [kwargs['pk']])
        return ImmediateHttpResponse(response=HttpAccepted())

    @staticmethod
    def _adapt_field(field):
        if "field_name" in field:
            field = field.copy()
            field["name"] = field.pop("field_name")
        return field

    def obj_create(self, bundle, request=None, **kwargs):
        adapt = self._adapt_field
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
            adapt = self._adapt_field
            bundle.obj.fields = [TypeField(**adapt(f)) for f in bundle.data['fields']]

        if 'item_attributes' in bundle.data:
            save = True
            bundle.obj.item_attributes = bundle.data['item_attributes']

        if save:
            bundle.obj.save()
        return bundle

    def detail_uri_kwargs(self, bundle_or_obj):
        return {'pk': get_obj(bundle_or_obj).id.hex}

    class Docs:
        summary = 'Lookup Tables'
        description = (
            'List, create, update or delete lookup tables (also known '
            'as fixtures) in a project space. A lookup table defines '
            'the fields available on its rows; see the lookup table '
            'item resources for the rows themselves. On update, '
            '`is_global`, `fields` and `item_attributes` are each '
            'independently optional -- a key left out of the request '
            'body keeps its current value; `tag` is the exception and '
            'must always be included, unchanged.'
        )
        examples = {'list_response': 'lookup_table/v1/list_response.json'}
        # obj_update() below raises tastypie's own NotFound (not a
        # domain-specific exception) when the identified table does not
        # exist, so Tastypie's create-on-PUT fallback genuinely fires
        # here. See operations._write_responses().
        put_creates_on_missing = True
        field_schemas = {
            'fields': {
                'items': {
                    'type': 'object',
                    'properties': {
                        'field_name': {'type': 'string'},
                        'properties': {
                            'type': 'array',
                            'items': {'type': 'string'},
                        },
                    },
                },
            },
            'item_attributes': {
                'items': {'type': 'string'},
            },
        }

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
    """Lookup Table Row API resource

    Example ``fields`` format:

        "fields": {
            "tree": {
                "field_list": [
                    {
                        "field_value": "pine",
                        "properties": {"family": "Pinaceae"}
                    }
                ]
            }
        }

    Note: the object containing "field_list" is superfluous and could
    be replaced with the "field_list" property value. Maybe in a
    API version?

    Example ``item_attributes`` format:

        "item_attributes": {
            "name": "Western White Pine Tree",
            "height": "30-50 meters",
        }
    """
    id = UUIDField(
        attribute='id',
        readonly=True,
        unique=True,
        help_text='Unique identifier of the lookup table item.',
    )
    data_type_id = UUIDField(
        attribute='table_id',
        help_text='Identifier of the lookup table this item belongs to. '
                  'Required when creating or updating a row; a request '
                  'without it is rejected.',
    )
    fields = FieldsDictField(
        attribute='fields',
        help_text='Field values for the row, keyed by field name. Each '
                  'field holds a field_list of one or more values, each '
                  'with its own properties (for example a language '
                  'code). Optional on create, defaulting to no fields. '
                  'On update, if provided, this replaces the entire '
                  'fields dict -- field names omitted from the '
                  'submitted value are removed from the row.',
    )
    item_attributes = tp_f.DictField(
        attribute='item_attributes',
        help_text='Attribute values for the row, keyed by attribute '
                  'name.',
    )

    validate_deserialized_data = JSONSchemaValidator({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "fields": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {"field_list": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "patternProperties": {
                                "^(field_)?value$": {"type": "string"},
                            },
                            "properties": {
                                "properties": {
                                    "type": "object",
                                    "additionalProperties": {"type": "string"},
                                },
                            },
                            "additionalProperties": False,
                            "oneOf": [
                                {"not": {"required": ["field_value"]}},
                                {"not": {"required": ["value"]}},
                            ],
                        },
                    }},
                    "additionalProperties": False,
                },
            },
            "item_attributes": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            }
        },
    })

    # It appears that sort_key is not included in any user facing UI. It is only defined as
    # the order of rows in the excel file when uploaded. We'll keep this behavior by incrementing
    # the sort key on new item creations
    sort_key = tp_f.IntegerField(
        attribute='sort_key',
        help_text='Order of this row within its lookup table, as '
                  'defined by the row order in the uploaded Excel '
                  'file. Not exposed in any user-facing UI. On create, '
                  'always assigned by the server as one greater than '
                  'the current maximum for the table; any value '
                  'submitted by the client is ignored.',
    )

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
            row = LookupTableRow.objects.get(id=kwargs['pk'], domain=kwargs['domain'])
        except LookupTableRow.DoesNotExist:
            raise NotFound('Lookup table item not found')
        table_id = row.table_id
        row.delete()
        clear_fixture_cache(row.domain, [table_id])
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
            clear_fixture_cache(kwargs['domain'], [data_type_id])
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
                clear_fixture_cache(bundle.obj.domain, [bundle.obj.table_id])

        return bundle

    def detail_uri_kwargs(self, bundle_or_obj):
        return {'pk': get_obj(bundle_or_obj).id.hex}

    class Docs:
        summary = 'Lookup Table Items'
        description = (
            'List, create, update or delete the rows (items) of a '
            'lookup table in a project space. On update, `data_type_id` '
            'must always be included; if the request body includes '
            'neither `fields` nor `item_attributes`, the row is left '
            'unmodified.'
        )
        # obj_update() above raises tastypie's own NotFound (not a
        # domain-specific exception) when the identified row does not
        # exist, so Tastypie's create-on-PUT fallback genuinely fires
        # here -- unlike user-v1 and location-v2, whose obj_update raises
        # something else. See operations._write_responses().
        put_creates_on_missing = True
        field_schemas = {
            'fields': {
                'additionalProperties': {
                    'type': 'object',
                    'properties': {
                        'field_list': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'field_value': {'type': 'string'},
                                    'properties': {
                                        'type': 'object',
                                        'additionalProperties': {
                                            'type': 'string',
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
            'item_attributes': {
                'additionalProperties': {'type': 'string'},
            },
        }

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
