from couchdbkit.exceptions import ResourceNotFound
from memoized import memoized

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DictProperty,
    Document,
    DocumentSchema,
    IntegerProperty,
    SchemaListProperty,
    StringListProperty,
    StringProperty,
)
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.migration import SyncCouchToSQLMixin

from corehq.apps.fixtures.dbaccessors import get_fixture_items_for_data_type


class FixtureTypeField(DocumentSchema):
    field_name = StringProperty()
    properties = StringListProperty()
    is_indexed = BooleanProperty(default=False)

    def __eq__(self, other):
        values = (self.field_name, self.properties, self.is_indexed)
        try:
            others = (other.field_name, other.properties, other.is_indexed)
        except AttributeError:
            return NotImplemented
        return values == others

    def __hash__(self):
        # NOTE mutable fields are used in this calculation, and changing
        # their values will break the hash contract. Hashing only works
        # on instances that will not be mutated.
        return hash((
            self.field_name,
            tuple(self.properties),
            self.is_indexed,
        ))

    @classmethod
    def from_sql(cls, type_field):
        return cls(
            field_name=type_field.name,
            properties=type_field.properties,
            is_indexed=type_field.is_indexed,
        )

    def to_sql(self):
        from .models import TypeField
        return TypeField(
            name=self.field_name,
            properties=self.properties,
            is_indexed=self.is_indexed,
        )


class FixtureDataType(SyncCouchToSQLMixin, Document):
    domain = StringProperty()
    is_global = BooleanProperty(default=False)
    tag = StringProperty()
    fields = SchemaListProperty(FixtureTypeField)
    item_attributes = StringListProperty()
    description = StringProperty()
    copy_from = StringProperty()

    @classmethod
    def wrap(cls, obj):
        if not obj["doc_type"] == "FixtureDataType":
            raise ResourceNotFound
        # Migrate fixtures without attributes on item-fields to fields with attributes
        if obj["fields"] and isinstance(obj['fields'][0], str):
            obj['fields'] = [{'field_name': f, 'properties': []} for f in obj['fields']]

        # Migrate fixtures without attributes on items to items with attributes
        if 'item_attributes' not in obj:
            obj['item_attributes'] = []

        return super(FixtureDataType, cls).wrap(obj)

    @property
    def _migration_couch_id(self):
        return self._id

    @classmethod
    def _migration_get_fields(cls):
        return [
            "domain",
            "is_global",
            "tag",
            "item_attributes",
        ]

    def _migration_sync_to_sql(self, sql_object, save=True):
        fields = self._sql_fields
        if sql_object.fields != fields:
            sql_object.fields = fields
        if sql_object.description != (self.description or ""):
            sql_object.description = self.description or ""
        super()._migration_sync_to_sql(sql_object, save=save)

    @property
    def _sql_fields(self):
        return [f.to_sql() for f in self.fields]

    @classmethod
    def _migration_get_sql_model_class(cls):
        from .models import LookupTable
        return LookupTable

    # support for old fields
    @property
    def fields_without_attributes(self):
        raise NotImplementedError("no longer used")

    @property
    def is_indexed(self):
        return any(f.is_indexed for f in self.fields)

    @classmethod
    def by_domain(cls, domain):
        raise NotImplementedError("no longer used")

    @classmethod
    def by_domain_tag(cls, domain, tag):
        raise NotImplementedError("no longer used")

    def recursive_delete(self, transaction):
        item_ids = []
        for item in get_fixture_items_for_data_type(self.domain, self.get_id):
            transaction.delete(item)
            item_ids.append(item.get_id)
        for item_id_chunk in chunked(item_ids, 1000):
            transaction.delete_all(FixtureOwnership.for_all_item_ids(item_id_chunk, self.domain))
        transaction.delete(self)
        # NOTE cache must be invalidated after transaction commit


class FixtureItemField(DocumentSchema):
    """
        "field_value": "Delhi_IN_HIN",
        "properties": {"lang": "hin"}
    """
    field_value = StringProperty()
    properties = DictProperty()

    def __eq__(self, other):
        values = (self.field_value, self.properties)
        try:
            other_values = (other.field_value, other.properties)
        except AttributeError:
            return NotImplemented
        return values == other_values

    def __hash__(self):
        # NOTE mutable fields are used in this calculation, and changing
        # their values will break the hash contract. Hashing only works
        # on instances that will not be mutated.
        return hash((self.field_value, tuple(sorted(self.properties.items()))))


class FieldList(DocumentSchema):
    """
        List of fields for different combinations of properties
    """
    field_list = SchemaListProperty(FixtureItemField)

    def to_api_json(self):
        value = self.to_json()
        del value['doc_type']
        for field in value['field_list']:
            del field['doc_type']
        return value

    def __eq__(self, other):
        value = self.field_list
        try:
            other_value = other.field_list
        except AttributeError:
            return NotImplemented
        return value == other_value

    def __hash__(self):
        # NOTE mutable fields are used in this calculation, and changing
        # their values will break the hash contract. Hashing only works
        # on instances that will not be mutated.
        return hash(tuple(self.field_list))


class FixtureDataItem(Document):
    """
    Example old Item:
        domain = "hq-domain"
        data_type_id = <id of state FixtureDataType>
        fields = {
            "country": "India",
            "state_name": "Delhi",
            "state_id": "DEL"
        }

    Example new Item with attributes:
        domain = "hq-domain"
        data_type_id = <id of state FixtureDataType>
        fields = {
            "country": {"field_list": [
                {"field_value": "India", "properties": {}},
            ]},
            "state_name": {"field_list": [
                {"field_value": "Delhi_IN_ENG", "properties": {"lang": "eng"}},
                {"field_value": "Delhi_IN_HIN", "properties": {"lang": "hin"}},
            ]},
            "state_id": {"field_list": [
                {"field_value": "DEL", "properties": {}}
            ]}
        }
    If one of field's 'properties' is an empty 'dict', the field has no attributes
    """
    domain = StringProperty()
    data_type_id = StringProperty()
    fields = DictProperty(FieldList)
    item_attributes = DictProperty()
    sort_key = IntegerProperty()

    @classmethod
    def wrap(cls, obj):
        if not obj["doc_type"] == "FixtureDataItem":
            raise ResourceNotFound
        if not obj["fields"]:
            return super(FixtureDataItem, cls).wrap(obj)

        # Migrate old basic fields to fields with attributes

        is_of_new_type = False
        fields_dict = {}

        def _is_new_type(field_val):
            old_types = (str, int, float)
            return field_val is not None and not isinstance(field_val, old_types)

        for field in obj['fields']:
            field_val = obj['fields'][field]
            if _is_new_type(field_val):
                # assumes all-or-nothing conversion of old types to new
                is_of_new_type = True
                break
            fields_dict[field] = {
                "field_list": [{
                    'field_value': str(field_val) if not isinstance(field_val, str) else field_val,
                    'properties': {}
                }]
            }
        if not is_of_new_type:
            obj['fields'] = fields_dict

        # Migrate fixture-items to have attributes
        if 'item_attributes' not in obj:
            obj['item_attributes'] = {}

        return super(FixtureDataItem, cls).wrap(obj)

    @property
    def fields_without_attributes(self):
        raise NotImplementedError("no longer used")

    @property
    def try_fields_without_attributes(self):
        raise NotImplementedError("no longer used")

    def add_owner(self, owner, owner_type, transaction=None):
        raise NotImplementedError("no longer used")

    def remove_owner(self, owner, owner_type):
        raise NotImplementedError("no longer used")

    def add_user(self, user, transaction=None):
        raise NotImplementedError("no longer used")

    def remove_user(self, user):
        raise NotImplementedError("no longer used")

    def add_group(self, group, transaction=None):
        raise NotImplementedError("no longer used")

    def remove_group(self, group):
        raise NotImplementedError("no longer used")

    def add_location(self, location, transaction=None):
        raise NotImplementedError("no longer used")

    def remove_location(self, location):
        raise NotImplementedError("no longer used")

    def get_groups(self, wrap=True):
        raise NotImplementedError("no longer used")

    @property
    @memoized
    def groups(self):
        raise NotImplementedError("no longer used")

    def get_users(self, wrap=True, include_groups=False):
        raise NotImplementedError("no longer used")

    def get_all_users(self, wrap=True):
        raise NotImplementedError("no longer used")

    @property
    @memoized
    def users(self):
        raise NotImplementedError("no longer used")

    @property
    @memoized
    def locations(self):
        raise NotImplementedError("no longer used")

    @classmethod
    def by_user(cls, user, include_docs=True):
        raise NotImplementedError("no longer used")

    @classmethod
    def by_group(cls, group, wrap=True):
        raise NotImplementedError("no longer used")

    @classmethod
    def by_data_type(cls, domain, data_type, bypass_cache=False):
        raise NotImplementedError("no longer used")

    @classmethod
    def by_domain(cls, domain):
        raise NotImplementedError("no longer used")

    @classmethod
    def by_field_value(cls, domain, data_type, field_name, field_value):
        raise NotImplementedError("no longer used")

    @classmethod
    def get_item_list(cls, domain, tag, **kw):
        raise NotImplementedError("no longer used")

    @classmethod
    def get_indexed_items(cls, domain, tag, index_field):
        raise NotImplementedError("no longer used")

    def delete_ownerships(self, transaction):
        ownerships = FixtureOwnership.by_item_id(self.get_id, self.domain)
        transaction.delete_all(ownerships)

    def recursive_delete(self, transaction):
        self.delete_ownerships(transaction)
        transaction.delete(self)


class FixtureOwnership(Document):
    domain = StringProperty()
    data_item_id = StringProperty()
    owner_id = StringProperty()
    owner_type = StringProperty(choices=['user', 'group', 'location'])

    @classmethod
    def by_item_id(cls, item_id, domain):
        ownerships = cls.view('fixtures/ownership',
            key=[domain, 'by data_item', item_id],
            include_docs=True,
            reduce=False,
        ).all()

        return ownerships

    @classmethod
    def for_all_item_ids(cls, item_ids, domain):
        ownerships = FixtureOwnership.view('fixtures/ownership',
            keys=[[domain, 'by data_item', item_id] for item_id in item_ids],
            include_docs=True,
            reduce=False
        ).all()

        return ownerships
