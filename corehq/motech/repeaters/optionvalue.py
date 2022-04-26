import attr

from dimagi.utils.parsing import json_format_datetime, string_to_utc_datetime


class DateTimeCoder:

    def to_json(value):
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
        if self.schema:
            return self.schema(obj.options.setdefault(self.name, {}))
        if self.name in obj.options:
            if self.coder:
                return self.coder.from_json(obj.options[self.name])
            return obj.options[self.name]
        if self.default is self.NOT_SET:
            raise AttributeError(self.name)
        value = self.default() if callable(self.default) else self.default
        obj.options[self.name] = value
        return value

    def __set__(self, obj, value):
        if self.choices and value not in self.choices:
            raise ValueError(f"{value!r} not in {self.choices!r}")
        if self.schema:
            if not isinstance(value, self.schema):
                raise TypeError(
                    f"Expected {self.name} to be of type {self.schema.__name__} but got {type(value).__name__}"
                )
            value = value.options
        if self.coder:
            value = self.coder.to_json(value)
        obj.options[self.name] = value


@attr.s
class OptionSchema:
    options = attr.ib()
