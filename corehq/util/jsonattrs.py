"""A Pythonic way to interact with structured JSON in Django models.

Why use this?

Rich object features such as default values, calculated properties, and
methods can be implemented centrally on an attrs class rather than
having that logic distributed, and probably duplicated, throughout the
application in every place where JSON values would be read and/or
written.

```py
@define
class Item:
    name = field()
    value = field(default=0)
    tags = field(factory=list)

    @property
    def proper_name(self):
        return self.name.title()


class Plane(models.Model):
    items = AttrsList(Item)


plane = Plane(items=[Item("line")])
plane.save()
# Saved `items` JSON: `[{"name": "line", "value": 0, "tags": []}]`

assert plane.items[0].proper_name == "Line"  # calculated property
```

Usage examples:

```py
@define
class Point:
    x = field()
    y = field()


class Plane(models.Model):

    # A dict of `<str>: Point(...)` items
    # JSON in the database looks like {"north": {"x": 0, "y": 1}, ...}
    points = AttrsDict(Point)

    # A list of `Point` objects
    # JSON in the database looks like [{"x": 0, "y": 1}, ...]
    coords = AttrsList(Point)

    # Nested collections are also possible:

    named_points = AttrsDict(list_of(Point))
    # JSON: {"north-west": [{"x": 0, "y": 1}, {"x": 1, "y": 0}, ...], ...}

    named_coords = AttrsList(dict_of(Point))
    # JSON: [{"north": {"x": 0, "y": 1}, "west": {"x": 1, "y": 0}, ...}, ...]
```

Attrs classes may implement `__jsonattrs_to_json__` (instance method) and
`__jsonattrs_from_json__` (class method) to perform custom conversions to and
from JSON. For example, these methods can be used to handle dates, times,
Decimal, and other non-JSON-serializable value types.

It is also possible to override `__jsonattrs_from_json__` on attrs types or
custom subclasses of `dict_of` and `list_of` to support lazy migrations of
legacy data. A note on lazy migrations: running a migration every time a row is
read is not free. While it may seem trivial for a single row, it adds up when
aggregated over thousands of rows read day after day. It may be a better long
term strategy to run the migration once and update all existing rows when the
data format changes. This allows the migration code to be removed and makes the
implementation simpler and more performant.

Things that may be added in the future:

- A Django field type that holds a single attrs class instance.
- Attrs field types for dates, times, Decimal, and other non-JSON-serializable
  value types.
- Support for migrating/converting the outer collection of `AttrsDict` and
  `AttrsList`.
"""
from attrs import asdict, define, field

from django.db.models import JSONField

__all__ = ["AttrsDict", "AttrsList", "dict_of", "list_of"]


class JsonAttrsField(JSONField):

    def __init__(self, *args, builder, **kw):
        super().__init__(*args, **kw)
        self.builder = builder

    def get_prep_value(self, value):
        return super().get_prep_value(self.builder.jsonify(value))

    def from_db_value(self, value, expression, connection):
        value = super().from_db_value(value, expression, connection)
        return self.builder.attrify(value)

    def value_to_string(self, obj):
        # Returns a JSON-serializable object for compatibility with
        # django.core.serializers.python.Serializer. Obviously this is
        # not strictly a string, but it's closer than the collection of
        # attrs instances returned by the default implementation.
        return self.builder.jsonify(self.value_from_object(obj))

    def deconstruct(self):
        # Returns a JSONField deconstruction to be used in migrations,
        # which do not need to know anything about attrs builders.
        name, path, args, kwargs = super().deconstruct()
        assert not args, (name, path, args, kwargs)
        assert "builder" not in kwargs, (name, path, args, kwargs)
        assert isinstance(self, JSONField), type(self).__mro__
        path = JSONField().deconstruct()[1]
        return name, path, args, kwargs

    def clone(self):
        # Assumes `self.builder` is immutable; it is shared by this
        # field and the clone.
        name, path, args, kwargs = super().deconstruct()
        assert not args, (name, path, args, kwargs)
        assert "builder" not in kwargs, (name, path, args, kwargs)
        return self.__class__(self.builder, **kwargs)


class AttrsDict(JsonAttrsField):
    """Dict field containing attrs values, saved to the database as JSON

    Dict keys are always strings because that is the only key type
    allowed in JSON. Dict values are attrs objects of the type specified
    by `value_type`
    """

    def __init__(self, value_type, /, **jsonfield_args):
        super().__init__(builder=AttrsDictBuilder(value_type), **jsonfield_args)


class AttrsList(JsonAttrsField):
    """List field containing attrs items, saved to the database as JSON

    List items are attrs objects of the type specified by `item_type`.
    """

    def __init__(self, item_type, /, **jsonfield_args):
        super().__init__(builder=AttrsListBuilder(item_type), **jsonfield_args)


@define
class AttrsListBuilder:
    attrs_type = field()

    def attrify(self, items):
        attrs_type = self.attrs_type
        if items is None:
            return items
        if hasattr(attrs_type, "__jsonattrs_from_json__"):
            from_json = attrs_type.__jsonattrs_from_json__
            return [from_json(item) for item in items]
        return [attrs_type(**item) for item in items]

    def jsonify(self, value):
        if not value:
            return value
        if hasattr(self.attrs_type, "__jsonattrs_to_json__"):
            to_json = self.attrs_type.__jsonattrs_to_json__
        else:
            to_json = asdict
        return [to_json(v) for v in value]


@define
class AttrsDictBuilder:
    attrs_type = field()

    def attrify(self, values):
        attrs_type = self.attrs_type
        if values is None:
            return values
        if hasattr(attrs_type, "__jsonattrs_from_json__"):
            from_json = attrs_type.__jsonattrs_from_json__
            return {key: from_json(value) for key, value in values.items()}
        return {key: attrs_type(**value) for key, value in values.items()}

    def jsonify(self, value):
        if not value:
            return value
        if hasattr(self.attrs_type, "__jsonattrs_to_json__"):
            to_json = self.attrs_type.__jsonattrs_to_json__
        else:
            to_json = asdict
        return {k: to_json(v) for k, v in value.items()}


@define
class dict_of:
    value_type = field()
    key_type = field(default=str)
    builder = field()

    @builder.default
    def _builder(self):
        return AttrsDictBuilder(self.value_type)

    def __jsonattrs_from_json__(self, value):
        self._check_none(value)
        return self.builder.attrify(value)

    def __jsonattrs_to_json__(self, value):
        self._check_none(value)
        return self.builder.jsonify(value)

    def _check_none(self, value):
        if value is None:
            typename = self.value_type.__name__
            raise ValueError(f"expected dict with {typename} values, got None")


@define
class list_of:
    item_type = field()
    builder = field()

    @builder.default
    def _builder(self):
        return AttrsListBuilder(self.item_type)

    def __jsonattrs_from_json__(self, value):
        self._check_none(value)
        return self.builder.attrify(value)

    def __jsonattrs_to_json__(self, value):
        self._check_none(value)
        return self.builder.jsonify(value)

    def _check_none(self, value):
        if value is None:
            typename = self.item_type.__name__
            raise ValueError(f"expected list of {typename}, got None")
