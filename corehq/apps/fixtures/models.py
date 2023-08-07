from datetime import datetime
from functools import reduce
from itertools import chain
from uuid import uuid4

from attrs import define, field
from django.db import models
from django.db.models.expressions import RawSQL

from corehq.apps.groups.models import Group
from corehq.sql_db.fields import CharIdField
from corehq.util.jsonattrs import AttrsDict, AttrsList, list_of

from .exceptions import FixtureVersionError

FIXTURE_BUCKET = 'domain-fixtures'


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


class LookupTable(models.Model):
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
    is_synced = models.BooleanField(default=False)

    class Meta:
        app_label = 'fixtures'
        unique_together = [('domain', 'tag')]

    @property
    def is_indexed(self):
        return any(f.is_indexed for f in self.fields)


class LookupTableRowManager(models.Manager):

    def iter_rows(self, domain, *, table_id=None, tag=None, **kw):
        """Get rows for lookup table

        Returned rows are sorted by sort_key.
        """
        if table_id is not None and tag is not None:
            raise TypeError("Too many arguments: 'table_id' and 'tag' are mutually exclusive.")
        if table_id is None:
            if tag is None:
                raise TypeError("Not enough arguments. Either 'table_id' or 'tag' is required.")
            try:
                table_id = LookupTable.objects.filter(
                    domain=domain, tag=tag).values("id").get()["id"]
            except LookupTable.DoesNotExist:
                return []
        where = models.Q(table_id=table_id)
        return self._iter_sorted(domain, where, **kw)

    def iter_by_user(self, user, **kw):
        """Get rows owned by the user, their location, or their group

        Returned rows are sorted by table_id and sort_key.
        """
        def make_conditions(owner_type, ids):
            return [models.Q(owner_type=owner_type, owner_id=x) for x in ids]

        group_ids = Group.by_user_id(user.user_id, wrap=False)
        locaction_ids = user.sql_location.path if user.sql_location else []
        where = models.Q(
            id__in=models.Subquery(
                LookupTableRowOwner.objects.filter(
                    reduce(models.Q.__or__, chain(
                        make_conditions(OwnerType.User, [user.user_id]),
                        make_conditions(OwnerType.Group, group_ids),
                        make_conditions(OwnerType.Location, locaction_ids),
                    )),
                    domain=user.domain,
                ).values("row_id")
            ),
        )
        return self._iter_sorted(user.domain, where, **kw)

    def _iter_sorted(self, domain, where, batch_size=1000):
        # Depends on ["domain", "table_id", "sort_key", "id"] index for
        # efficient pagination and sorting.
        query = self.filter(where, domain=domain).order_by("table_id", "sort_key", "id")
        next_page = models.Q()
        while True:
            results = query.filter(next_page)[:batch_size]
            yield from results
            if len(results) < batch_size:
                break
            row = results._result_cache[-1]
            next_page = models.Q(
                table_id=row.table_id,
                sort_key=row.sort_key,
                id__gt=row.id,
            ) | models.Q(
                table_id=row.table_id,
                sort_key__gt=row.sort_key
            ) | models.Q(
                table_id__gt=row.table_id,
            )

    def with_value(self, domain, table_id, field_name, value):
        """Get all rows having a field matching the given name/value pair

        WARNING may be inefficient for large lookup tables because field
        values are not indexed so the query will scan every row in the
        table (that is, all rows matching domain and table_id).
        """
        # Postgres 12 can replace the subquery with a WHERE predicate like:
        # fields @@ '$.field_name[*] ? (@.value == "value")'
        row_ids = RawSQL(f"""
            SELECT row.id FROM {self.model._meta.db_table} AS row,
                jsonb_to_recordset(row.fields->%s) AS val(value text)
            WHERE row.domain = %s AND row.table_id = %s AND val.value = %s
        """, [field_name, domain, table_id, value])
        return self.filter(id__in=row_ids)


@define
class Field:
    value = field()
    properties = field(factory=dict)

    def __eq__(self, other):
        values = (self.value, self.properties)
        try:
            other_values = (other.value, other.properties)
        except AttributeError:
            return NotImplemented
        return values == other_values

    def __hash__(self):
        # NOTE mutable fields are used in this calculation, and changing
        # their values will break the hash contract. Hashing only works
        # on instances that will not be mutated.
        return hash((self.value, tuple(sorted(self.properties.items()))))


# on_delete=DB_CASCADE denotes ON DELETE CASCADE in the database. The
# constraints are configured in a migration. Note that Django signals
# will not fire on records deleted via cascade.
DB_CASCADE = models.DO_NOTHING


class LookupTableRow(models.Model):
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
    objects = LookupTableRowManager()

    id = models.UUIDField(primary_key=True, default=uuid4)
    domain = CharIdField(max_length=126, db_index=True, default=None)
    table = models.ForeignKey(LookupTable, on_delete=DB_CASCADE, db_constraint=False)
    fields = AttrsDict(list_of(Field), default=dict)
    item_attributes = models.JSONField(default=dict)
    sort_key = models.IntegerField()

    class Meta:
        app_label = 'fixtures'
        indexes = [
            models.Index(fields=["domain", "table_id", "sort_key", "id"]),
        ]

    @property
    def fields_without_attributes(self):
        """Get a dict of field names mapped to respective field values

        :raises: ``FixtureVersionError`` if any field has more than one value.
        :raises: ``IndexError`` if any field does not have at least one value.
        """
        fields = {}
        for name, values in self.fields.items():
            # if the field has properties, a unique field_val can't be generated for FixtureItem
            if len(values) > 1:
                raise FixtureVersionError(
                    "This method is not supported for fields with properties."
                    f" field '{name}' has properties")
            fields[name] = values[0].value
        return fields


class OwnerType(models.IntegerChoices):
    User = 0
    Group = 1
    Location = 2

    @classmethod
    def from_string(cls, value):
        return getattr(cls, value.title())


class LookupTableRowOwner(models.Model):
    domain = CharIdField(max_length=126, default=None)
    owner_type = models.PositiveSmallIntegerField(choices=OwnerType.choices)
    owner_id = CharIdField(max_length=126, default=None)
    row = models.ForeignKey(LookupTableRow, on_delete=DB_CASCADE, db_constraint=False)

    class Meta:
        app_label = 'fixtures'
        indexes = [
            models.Index(fields=["domain", "owner_type", "owner_id"])
        ]


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
