from decimal import Decimal
from uuid import UUID

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
from corehq.apps.fixtures.exceptions import FixtureVersionError
from corehq.apps.fixtures.utils import remove_deleted_ownerships
from corehq.apps.groups.models import Group

FIXTURE_BUCKET = 'domain-fixtures'


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
        for item in FixtureDataItem.by_data_type(self.domain, self.get_id, bypass_cache=True):
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


class FixtureDataItem(SyncCouchToSQLMixin, Document):
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
    def _migration_couch_id(self):
        return self._id

    @classmethod
    def _migration_get_fields(cls):
        return ["domain"]

    def _migration_sync_to_sql(self, sql_object, save=True):
        if sql_object.table_id is None or sql_object.table_id != UUID(self.data_type_id):
            sql_object.table_id = UUID(self.data_type_id)
        fields = self._sql_fields
        if sql_object.fields != fields:
            sql_object.fields = fields
        attributes = self._sql_item_attributes
        if sql_object.item_attributes != attributes:
            sql_object.item_attributes = attributes
        sql_object.sort_key = self.sort_key or 0
        super()._migration_sync_to_sql(sql_object, save=save)

    @property
    def _sql_fields(self):
        from .models import Field
        return {
            name: [
                Field(val.field_value, val.properties)
                for val in values.field_list
            ]
            for name, values in self.fields.items()
        }

    @property
    def _sql_item_attributes(self):
        def convert(value):
            if isinstance(value, Decimal):
                return str(value)
            return value
        return {name: convert(value) for name, value in self.item_attributes.items()}

    @classmethod
    def _migration_get_sql_model_class(cls):
        from .models import LookupTableRow
        return LookupTableRow

    @property
    def fields_without_attributes(self):
        fields = {}
        for field in self.fields:
            # if the field has properties, a unique field_val can't be generated for FixtureItem
            if len(self.fields[field].field_list) > 1:
                raise FixtureVersionError("This method is not supported for fields with properties."
                                          " field '%s' has properties" % field)
            fields[field] = self.fields[field].field_list[0].field_value
        return fields

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
        """
        This method returns all fixture data items owned by the user, their location, or their group.

        :param include_docs: whether to return the fixture data item dicts or just a set of ids
        """
        group_ids = Group.by_user_id(user.user_id, wrap=False)
        loc_ids = user.sql_location.path if user.sql_location else []

        def make_keys(owner_type, ids):
            return [[user.domain, 'data_item by {}'.format(owner_type), id_]
                    for id_ in ids]

        fixture_ids = set(
            FixtureOwnership.get_db().view('fixtures/ownership',
                keys=(make_keys('user', [user.user_id])
                      + make_keys('group', group_ids)
                      + make_keys('location', loc_ids)),
                reduce=False,
                wrapper=lambda r: r['value'],
            )
        )
        if include_docs:
            results = cls.get_db().view('_all_docs', keys=list(fixture_ids), include_docs=True)

            # sort the results into those corresponding to real documents
            # and those corresponding to deleted or non-existent documents
            docs = []
            deleted_fixture_ids = set()

            for result in results:
                if result.get('doc'):
                    docs.append(result['doc'])
                elif result.get('error'):
                    assert result['error'] == 'not_found'
                    deleted_fixture_ids.add(result['key'])
                else:
                    assert result['value']['deleted'] is True
                    deleted_fixture_ids.add(result['id'])
            if deleted_fixture_ids:
                # delete ownership documents pointing deleted/non-existent fixture documents
                # this cleanup is necessary since we used to not do this
                remove_deleted_ownerships.delay(list(deleted_fixture_ids), user.domain)
            return docs
        else:
            return fixture_ids

    @classmethod
    def by_group(cls, group, wrap=True):
        raise NotImplementedError("no longer used")

    @classmethod
    def by_data_type(cls, domain, data_type, bypass_cache=False):
        return get_fixture_items_for_data_type(domain, _id_from_doc(data_type), bypass_cache)

    @classmethod
    def by_domain(cls, domain):
        raise NotImplementedError("no longer used")

    @classmethod
    def by_field_value(cls, domain, data_type, field_name, field_value):
        data_type_id = _id_from_doc(data_type)
        return cls.view('fixtures/data_items_by_field_value', key=[domain, data_type_id, field_name, field_value],
                        reduce=False, include_docs=True)

    @classmethod
    def get_item_list(cls, domain, tag, **kw):
        from .models import LookupTable
        try:
            data_type = LookupTable.objects.by_domain_tag(domain, tag)
        except LookupTable.DoesNotExist:
            return []
        return cls.by_data_type(domain, data_type, **kw)

    @classmethod
    def get_indexed_items(cls, domain, tag, index_field):
        """
        Looks up an item list and converts to mapping from `index_field`
        to a dict of all fields for that item.

            fixtures = FixtureDataItem.get_indexed_items('my_domain',
                'item_list_tag', 'index_field')
            result = fixtures['index_val']['result_field']
        """
        fixtures = cls.get_item_list(domain, tag)
        return dict((f.fields_without_attributes[index_field], f.fields_without_attributes) for f in fixtures)

    def delete_ownerships(self, transaction):
        ownerships = FixtureOwnership.by_item_id(self.get_id, self.domain)
        transaction.delete_all(ownerships)

    def recursive_delete(self, transaction):
        self.delete_ownerships(transaction)
        transaction.delete(self)


def _id_from_doc(doc_or_doc_id):
    if isinstance(doc_or_doc_id, str):
        doc_id = doc_or_doc_id
    else:
        # ._migration_couch_id was used so usages of this function are
        # revisited or removed by the time the migration is complete.
        doc_id = doc_or_doc_id._migration_couch_id if doc_or_doc_id else None
    return doc_id


class FixtureOwnership(SyncCouchToSQLMixin, Document):
    domain = StringProperty()
    data_item_id = StringProperty()
    owner_id = StringProperty()
    owner_type = StringProperty(choices=['user', 'group', 'location'])

    @property
    def _migration_couch_id(self):
        return self._id

    @classmethod
    def _migration_get_fields(cls):
        return [
            "domain",
            "owner_id",
        ]

    def _migration_sync_to_sql(self, sql_object, save=True):
        from .models import OwnerType
        if sql_object.row_id is None or sql_object.row_id != UUID(self.data_item_id):
            sql_object.row_id = UUID(self.data_item_id)
        if OwnerType.from_string(self.owner_type) != sql_object.owner_type:
            sql_object.owner_type = OwnerType.from_string(self.owner_type)
        super()._migration_sync_to_sql(sql_object, save=save)

    @classmethod
    def _migration_get_sql_model_class(cls):
        from .models import LookupTableRowOwner
        return LookupTableRowOwner

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
