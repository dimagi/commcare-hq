import attr


class OptionValue(property):

    NOT_SET = object()

    def __init__(
        self,
        default=NOT_SET,
        choices=None,
        schema=None,
        schema_list=None
    ):
        if schema and default is not self.NOT_SET:
            raise ValueError("default not allowed with schema")
        self.default = default
        self.choices = choices
        self.schema = schema
        self.schema_list = schema_list

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.schema:
            return self.schema(obj.options.setdefault(self.name, {}))
        if self.schema_list:
            list_val = obj.options.setdefault(self.name, [])
            for index in range(len(list_val)):
                list_val[index] = self.schema_list(list_val[index])
            return list_val
        if self.name in obj.options:
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
        if self.schema_list:
            obj_list = []
            for obj_schema in value:
                if not isinstance(obj_schema, self.schema_list):
                    raise TypeError(
                        f"""Expected {self.name} to be of type {self.schema_list.__name__}
                        but got {type(obj_schema).__name__}"""
                    )
                obj_list.append(obj_schema.options)
            value = obj_list

        obj.options[self.name] = value


@attr.s
class OptionSchema:
    options = attr.ib()
