"""Mapping from ``jsonobject`` request models to JSON Schema."""

import jsonobject

PROPERTY_TYPES = {
    jsonobject.StringProperty: {'type': 'string'},
    jsonobject.BooleanProperty: {'type': 'boolean'},
    jsonobject.IntegerProperty: {'type': 'integer'},
    jsonobject.FloatProperty: {'type': 'number'},
    jsonobject.DecimalProperty: {'type': 'string', 'format': 'decimal'},
    jsonobject.DateProperty: {'type': 'string', 'format': 'date'},
    jsonobject.DateTimeProperty: {'type': 'string', 'format': 'date-time'},
}


def _property_schema(prop):
    for prop_type, schema in PROPERTY_TYPES.items():
        if isinstance(prop, prop_type):
            schema = dict(schema)
            break
    else:
        schema = None

    if isinstance(prop, jsonobject.DictProperty):
        schema = {'type': 'object'}
        item_wrapper = getattr(prop, 'item_wrapper', None)
        item_type = getattr(item_wrapper, 'item_type', None)
        if item_type is not None and issubclass(
            item_type, jsonobject.JsonObject
        ):
            schema['additionalProperties'] = jsonobject_to_schema(item_type)
        else:
            schema['additionalProperties'] = True
    elif isinstance(prop, jsonobject.ListProperty):
        schema = {'type': 'array', 'items': {}}
    elif isinstance(prop, jsonobject.ObjectProperty):
        return jsonobject_to_schema(prop.item_type)

    if schema is None:
        return {}

    choices = getattr(prop, 'choices', None)
    if choices:
        schema['enum'] = list(choices)

    default = _default_value(prop)
    if default is not None:
        schema['default'] = default
    return schema


def _default_value(prop):
    """The property's default, or ``None`` if it has none.

    ``jsonobject`` wraps every declared default in a zero-argument callable,
    so the value has to be computed rather than read.

    A default that cannot be computed is documented as absent rather than
    guessed at. The catch is deliberately broad because the callable is
    written by whoever declared the model and may raise anything -- but it
    covers only the call, and its only effect is a missing ``default`` in
    the published schema, never a wrong one. It has not fired for any
    model documented today: every declared default is one of jsonobject's
    own trivial callables. If a model ever gains a default that needs
    request context to compute, this is what keeps the spec honest about
    it instead of failing the build.
    """
    default = getattr(prop, 'default', None)
    if default is None:
        return None
    if callable(default):
        try:
            default = default()
        except Exception:
            return None
    return default if default not in (None, (), {}, []) else None


def jsonobject_to_schema(cls):
    """JSON Schema for a ``jsonobject.JsonObject`` subclass."""
    properties = {}
    required = []
    for key, prop in cls._properties_by_key.items():
        properties[key] = _property_schema(prop)
        if getattr(prop, 'required', False):
            required.append(key)
    schema = {'type': 'object', 'properties': properties}
    if required:
        schema['required'] = sorted(required)
    return schema
