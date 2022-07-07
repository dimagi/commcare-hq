from datetime import datetime
from uuid import UUID, uuid4

from attrs import define, field
from django.db import models

from dimagi.utils.couch.migration import SyncSQLToCouchMixin

from corehq.sql_db.fields import CharIdField
from corehq.util.jsonattrs import AttrsList

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

    def _migration_sync_to_couch(self, couch_object):
        if self.fields != couch_object._sql_fields:
            couch_object.fields = [FixtureTypeField.from_sql(f) for f in self.fields]
        if self.description != (couch_object.description or ""):
            couch_object.description = self.description
        super()._migration_sync_to_couch(couch_object)

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
