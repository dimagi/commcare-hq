"""
The OptionValue property
========================

``OptionValue`` is a subclass of ``property``. It is used for managing
the values in a dictionary named "options" belonging to the object that
the ``OptionValue`` is a property of.

That sounds more complicated than it is. An example can help. Imagine
the following ``Meal`` class to manage meals on an airline::

    >>> from attrs import define, field
    >>> @define
    ... class Meal:
    ...     options = field(factory=dict)
    ...     dish = OptionValue()
    ...     category = OptionValue(choices=["chicken", "beef", "vegan"])

The ``dish`` and ``category`` OptionValues will manage values in the
``options`` dictionary named ``'dish'`` and ``'category'`` respectively.

Usage would work like this::

    >>> my_meal = Meal()
    >>> my_meal.dish = "Coronation Chicken"
    >>> my_meal.options
    {'dish': 'Coronation Chicken'}
    >>> my_meal.category = "chicken"
    >>> my_meal.options
    {'dish': 'Coronation Chicken', 'category': 'chicken'}


Why?
----

The purpose of the ``OptionValue`` class is to allow arbitrary
properties on Django models and their subclasses to be stored in a
JSON field. You can find examples in ``CaseRepeater``, which has
options "version", "white_listed_case_types" and "black_listed_users",
and its subclass ``Dhis2EntityRepeater``, which has an additional
option, "dhis2_entity_config". Values for all of these options are
persisted by their base class, ``Repeater.options``, defined as
``JSONField(default=dict)``.

"""
from dimagi.utils.parsing import ISO_DATETIME_FORMAT, json_format_datetime, string_to_utc_datetime
from datetime import datetime


class DateTimeCoder:

    def to_json(value):
        if type(value) == str:
            try:
                datetime.strptime(value, ISO_DATETIME_FORMAT)
                return value
            except ValueError:
                raise ValueError(f"{value} should be a valid datetime of Format {ISO_DATETIME_FORMAT}")
        return json_format_datetime(value) if value is not None else None

    def from_json(value):
        return string_to_utc_datetime(value) if value is not None else None


class OptionValue(property):

    NOT_SET = object()

    def __init__(
        self,
        default=NOT_SET,
        choices=None,
        schema=None,
        coder=None,
    ):
        if schema and default is not self.NOT_SET:
            raise ValueError("default not allowed with schema")
        self.default = default
        self.choices = choices
        self.schema = schema
        self.coder = coder

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        _assert_options(obj)
        if self.schema:
            return self.schema(obj.options.setdefault(self.name, {}))
        if self.name in obj.options:
            if self.coder:
                return self.coder.from_json(obj.options[self.name])
            return obj.options[self.name]
        value = self.get_default_value()
        obj.options[self.name] = value
        return value

    def __set__(self, obj, value):
        if self.choices and value not in self.choices:
            raise ValueError(f"{value!r} not in {self.choices!r}")
        _assert_options(obj)
        if self.schema:
            if not isinstance(value, self.schema):
                raise TypeError(
                    f"Expected {self.name} to be of type {self.schema.__name__} but got {type(value).__name__}"
                )
            value = value.options
        if self.coder:
            value = self.coder.to_json(value)
        obj.options[self.name] = value

    def get_default_value(self):
        if self.default is self.NOT_SET:
            raise AttributeError(self.name)
        return self.default() if callable(self.default) else self.default


def _assert_options(obj):
    assert hasattr(obj, 'options') and isinstance(obj.options, dict), \
        f"{obj!r} needs an 'options' dict to use OptionValue"
