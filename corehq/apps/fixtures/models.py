from datetime import datetime
from uuid import UUID, uuid4

from attrs import define, field
from django.db import models

from dimagi.utils.couch.migration import SyncSQLToCouchMixin

from corehq.sql_db.fields import CharIdField
from corehq.util.jsonattrs import AttrsDict, AttrsList, list_of

from .couchmodels import (  # noqa: F401
    _id_from_doc,
    FIXTURE_BUCKET,
    FieldList,
    FixtureDataItem,
    FixtureDataType,
    FixtureItemField,
    FixtureOwnership,
    FixtureTypeField,
)


class LookupTableManager(models.Manager):

    def by_domain(self, domain_name):
        return self.filter(domain=domain_name)

    def by_domain_tag(self, domain_name, tag):
        """Get lookup table by domain and tag"""
        return self.get(domain=domain_name, tag=tag)

    def domain_tag_exists(self, domain_name, tag):
        return self.filter(domain=domain_name, tag=tag).exists()


@define
class Alias:
    name = field()

    def __get__(self, obj, owner=None):
        return self if obj is None else getattr(obj, self.name)

    def __set__(self, obj, value):
        setattr(obj, self.name, value)


@define
class TypeField:
    name = field()
    properties = field(factory=list)
    is_indexed = field(default=False)
    field_name = Alias("name")

    def __hash__(self):
        # NOTE mutable fields are used in this calculation, and changing
        # their values will break the hash contract. Hashing only works
        # on instances that will not be mutated.
        return hash((self.name, tuple(self.properties), self.is_indexed))


class LookupTable(SyncSQLToCouchMixin, models.Model):
    """Lookup Table

    `fields` structure:
    ```py
    [
        {
            "name": "country",
            "properties": [],
            "is_indexed": True,
        },
        {
            "name": "state_name",
            "properties": ["lang"],
            "is_indexed": False,
        },
        ...
    ]
    ```
    """
    objects = LookupTableManager()

    id = models.UUIDField(primary_key=True, default=uuid4)
    domain = CharIdField(max_length=126, db_index=True, default=None)
    is_global = models.BooleanField(default=False)
    tag = CharIdField(max_length=32, default=None)
    fields = AttrsList(TypeField, default=list)
    item_attributes = models.JSONField(default=list)
    description = models.CharField(max_length=255, default="")

    class Meta:
        app_label = 'fixtures'
        unique_together = [('domain', 'tag')]

    _migration_couch_id_name = "id"

    @property
    def _migration_couch_id(self):
        return self.id.hex

    @_migration_couch_id.setter
    def _migration_couch_id(self, value):
        self.id = UUID(value)

    @classmethod
    def _migration_get_fields(cls):
        return [
            "domain",
            "is_global",
            "tag",
            "item_attributes",
        ]

    def _migration_sync_to_couch(self, couch_object, save=True):
        if self.fields != couch_object._sql_fields:
            couch_object.fields = [FixtureTypeField.from_sql(f) for f in self.fields]
        if self.description != (couch_object.description or ""):
            couch_object.description = self.description
        super()._migration_sync_to_couch(couch_object, save=save)

    @classmethod
    def _migration_get_couch_model_class(cls):
        return FixtureDataType

    def _migration_get_or_create_couch_object(self):
        cls = self._migration_get_couch_model_class()
        obj = self._migration_get_couch_object()
        if obj is None:
            obj = cls(_id=self._migration_couch_id)
            obj.save(sync_to_sql=False)
        return obj

    def clear_caches(self):
        pass


@define
class Field:
    value = field()
    properties = field(factory=dict)


# on_delete=DB_CASCADE denotes ON DELETE CASCADE in the database. The
# constraints are configured in a migration. Note that Django signals
# will not fire on records deleted via cascade.
DB_CASCADE = models.DO_NOTHING


class LookupTableRow(SyncSQLToCouchMixin, models.Model):
    """Lookup Table Row data model

    `fields` structure:
    ```py
    {
        "country": [
            {"value": "India", "properties": {}},
        ],
        "state_name": [
            {"value": "Delhi_IN_ENG", "properties": {"lang": "eng"}},
            {"value": "Delhi_IN_HIN", "properties": {"lang": "hin"}},
        ],
        "state_id": [
            {"value": "DEL", "properties": {}}
        ],
    }
    ```

    `item_attributes` structure:
    ```py
    {
        "attr1": "value1",
        "attr2": "value2",
    }
    ```
    """
    id = models.UUIDField(primary_key=True, default=uuid4)
    domain = CharIdField(max_length=126, db_index=True, default=None)
    table = models.ForeignKey(LookupTable, on_delete=DB_CASCADE)
    fields = AttrsDict(list_of(Field), default=dict)
    item_attributes = models.JSONField(default=dict)
    sort_key = models.IntegerField()

    class Meta:
        app_label = 'fixtures'
        indexes = [
            models.Index(fields=["domain", "table_id", "sort_key", "id"]),
        ]

    _migration_couch_id_name = "id"

    @property
    def _migration_couch_id(self):
        return self.id.hex

    @_migration_couch_id.setter
    def _migration_couch_id(self, value):
        self.id = UUID(value)

    @classmethod
    def _migration_get_fields(cls):
        return ["domain", "sort_key"]

    def _migration_sync_to_couch(self, couch_object, save=True):
        if couch_object.data_type_id is None or UUID(couch_object.data_type_id) != self.table_id:
            couch_object.data_type_id = self.table_id.hex
        if self.fields != couch_object._sql_fields:
            couch_object.fields = {
                name: FieldList(field_list=[
                    FixtureItemField(
                        field_value=val.value,
                        properties=val.properties,
                    ) for val in values
                ]) for name, values in self.fields.items()
            }
        if self.item_attributes != couch_object._sql_item_attributes:
            couch_object.item_attributes = self.item_attributes
        super()._migration_sync_to_couch(couch_object, save=save)

    @classmethod
    def _migration_get_couch_model_class(cls):
        return FixtureDataItem

    def _migration_get_or_create_couch_object(self):
        cls = self._migration_get_couch_model_class()
        obj = self._migration_get_couch_object()
        if obj is None:
            obj = cls(_id=self._migration_couch_id)
            obj.save(sync_to_sql=False)
        return obj


class OwnerType(models.IntegerChoices):
    User = 0
    Group = 1
    Location = 2

    @classmethod
    def from_string(cls, value):
        return getattr(cls, value.title())


class LookupTableRowOwner(SyncSQLToCouchMixin, models.Model):
    domain = CharIdField(max_length=126, default=None)
    owner_type = models.PositiveSmallIntegerField(choices=OwnerType.choices)
    owner_id = CharIdField(max_length=126, default=None)
    row = models.ForeignKey(LookupTableRow, on_delete=DB_CASCADE)
    couch_id = CharIdField(max_length=126, null=True, db_index=True)

    class Meta:
        app_label = 'fixtures'
        indexes = [
            models.Index(fields=["domain", "owner_type", "owner_id"])
        ]

    @classmethod
    def _migration_get_fields(cls):
        return ["domain", "owner_id"]

    def _migration_sync_to_couch(self, couch_object, save=True):
        if couch_object.data_item_id is None or UUID(couch_object.data_item_id) != self.row_id:
            couch_object.data_item_id = self.row_id.hex
        if OwnerType(self.owner_type).name.lower() != couch_object.owner_type:
            couch_object.owner_type = OwnerType(self.owner_type).name.lower()
        super()._migration_sync_to_couch(couch_object, save=save)

    @classmethod
    def _migration_get_couch_model_class(cls):
        return FixtureOwnership


class UserLookupTableType:
    LOCATION = 1
    CHOICES = (
        (LOCATION, "Location"),
    )


class UserLookupTableStatus(models.Model):
    """Keeps track of when a user needs to re-sync a fixture"""
    id = models.AutoField(primary_key=True, verbose_name="ID", auto_created=True)
    user_id = models.CharField(max_length=100, db_index=True)
    fixture_type = models.PositiveSmallIntegerField(choices=UserLookupTableType.CHOICES)
    last_modified = models.DateTimeField()

    DEFAULT_LAST_MODIFIED = datetime.min

    class Meta:
        app_label = 'fixtures'
        db_table = 'fixtures_userfixturestatus'
        unique_together = ("user_id", "fixture_type")
