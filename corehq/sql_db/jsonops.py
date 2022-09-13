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

from django.db.models.expressions import Expression, Func, RawSQL, Value
from django.db.models import JSONField


class JsonDelete(Func):
    """Delete item(s) from JSONB value

    A Django expression for the `-` operator as it pertains to JSONB values.

    :param expression: JSONB field name or value expression.
    :param *items: Names of items to delete.
    """
    function = "-"
    template = "%(expressions)s::jsonb %(function)s '{%(items)s}'::text[]"
    arity = 1

    def __init__(self, expression, *items):
        if isinstance(expression, JsonDelete):
            items = (expression.extra["items"],) + items
            expression, = expression.source_expressions
        items = ",".join(items)
        if "'" in items:
            raise ValueError(f"invalid items: {items!r}")
        super().__init__(expression, output_field=JSONField(), items=items)


class JsonGet(Func):
    """Get item from JSON or JSONB value

    A Django expression for the `->` operator as it pertains to JSON and
    JSONB values.

    :param expression: JSON/JSONB field name or value expression.
    :param field: Name of item to get.
    """
    function = "->"
    template = "%(expressions)s%(function)s'%(field_name)s'"
    arity = 1

    def __init__(self, expression, field):
        if not isinstance(field, str) or "'" in field:
            raise ValueError(f"invalid field: {field!r}")
        super().__init__(expression, output_field=JSONField(), field_name=field)


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
        path_items = ",".join(_int_str(p) for p in path)
        if "'" in path_items:
            raise ValueError(f"invalid path: {path_items!r}")
        if not isinstance(new_value, Expression):
            new_value = Value(json.dumps(new_value))
        super().__init__(
            expression,
            RawSQL("'{%s}'" % path_items, ()),
            new_value,
            output_field=JSONField(),
            create_missing="true" if create_missing else "false",
        )


def _int_str(arg):
    return str(arg) if isinstance(arg, int) else arg
