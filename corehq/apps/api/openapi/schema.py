"""Mapping from Tastypie field metadata to OpenAPI 3.0.3 schema objects."""

from tastypie.fields import NOT_PROVIDED

from corehq.apps.api.openapi.docs import field_description

TYPE_MAP = {
    'string': {'type': 'string'},
    'integer': {'type': 'integer'},
    'float': {'type': 'number'},
    'decimal': {'type': 'string', 'format': 'decimal'},
    'boolean': {'type': 'boolean'},
    'list': {'type': 'array', 'items': {}},
    'dict': {'type': 'object', 'additionalProperties': True},
    'date': {'type': 'string', 'format': 'date'},
    'datetime': {'type': 'string', 'format': 'date-time'},
    'time': {'type': 'string', 'format': 'time'},
    'related': {'type': 'string', 'format': 'uri'},
}


def field_to_schema(field_info, *, override=None):
    """Convert one ``build_schema()`` field entry to a schema object.

    ``override`` is merged last, so a hand-written ``Docs.field_schemas``
    entry wins over anything derived from the field.
    """
    schema = dict(TYPE_MAP.get(field_info['type'], {}))

    description = field_description(field_info.get('help_text'))
    if description:
        schema['description'] = description

    if field_info.get('nullable'):
        schema['nullable'] = True
    if field_info.get('readonly'):
        schema['readOnly'] = True

    default = field_info.get('default')
    if default is not NOT_PROVIDED and not callable(default):
        schema['default'] = default

    if override:
        schema.update(override)
    return schema
