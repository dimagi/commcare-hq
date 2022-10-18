"""
JSON and JSONB functions and operators for PostgreSQL

Reference: https://www.postgresql.org/docs/10/functions-json.html

In particular, `JsonGet`, `JsonSet`, and `JsonDelete` can be nested to perform
multiple transformation operations on a JSONB value.

For example, the following expression renames the top-level "values" key to
"items" and removes the "score" key/value pair from a table column named
"json_data":

```py
transformed_data = JsonDelete(
    JsonSet(
        JsonDelete("json_data", "values"),
        ["items"],
        JsonGet("json_data", "values"),
    ),
    "score",
)
SomeModel.objects.filter(...).update(json_data=transformed_data)

# Example "json_data" before/after above transformation
# Before: {"values": [1, 2, 3], "other": "something", "score": 3}
# After:  {"items": [1, 2, 3], "other": "something"}
```
"""
import json

from django.db.models.expressions import Expression, Func, Value
from django.db.models import JSONField


class JsonDelete(Func):
    """Delete item(s) from JSONB value

    A Django expression for the `-` operator as it pertains to JSONB values.

    Example: '{"a": "b", "c": "d"}'::jsonb - '{a,c}'::text[]

    :param expression: JSONB field name or value expression.
    :param *keys: Names of items to delete.
    """
    arg_joiner = " - "
    template = "%(expressions)s"
    arity = 2

    def __init__(self, expression, *keys):
        _validate(keys, [str])
        keys = list(keys)
        if isinstance(expression, JsonDelete):
            expression, keys_value = expression.source_expressions
            keys = keys_value.value + keys
        super().__init__(expression, Value(keys), output_field=JSONField())


class JsonGet(Func):
    """Get item from JSON or JSONB value

    A Django expression for the `->` operator as it pertains to JSON and
    JSONB values.

    :param expression: JSON/JSONB field name or value expression.
    :param field: Name or index of item to get.
    """
    arg_joiner = "->"
    template = "%(expressions)s"
    arity = 2

    def __init__(self, expression, field):
        super().__init__(expression, Value(field), output_field=JSONField())


class JsonSet(Func):
    """Replace value at path in JSONB value

    A Django expression for the `jsonb_set()` function.

    :param expression: JSONB field name or value expression.
    :param path: Sequence of keys or indexes representing the path of
        the value in `expression` to be replaced.
    :param new_value: JSON-serializable value or expression.
    :param create_missing: Add value if it is missing (default: True).
    """
    function = "jsonb_set"
    template = "%(function)s(%(expressions)s, %(create_missing)s)"
    arity = 3

    def __init__(self, expression, path, new_value, create_missing=True):
        _validate(path, (int, str))
        path_items = [_int_str(p) for p in path]
        if not isinstance(new_value, Expression):
            new_value = Value(json.dumps(new_value))
        super().__init__(
            expression,
            Value(path_items),
            new_value,
            output_field=JSONField(),
            create_missing="true" if create_missing else "false",
        )


def _validate(values, types):
    types = tuple(types)
    if not all(isinstance(i, types) for i in values):
        expect = "|".join(t.__name__ for t in types)
        got = ", ".join(type(v).__name__ for v in values)
        raise ValueError(f"expected {expect} value(s), got ({got})")


def _int_str(arg):
    return str(arg) if isinstance(arg, int) else arg
