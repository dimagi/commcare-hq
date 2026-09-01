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

# Python types accepted for a ``default`` value under each JSON Schema
# ``type``. Tastypie sometimes reports a default that does not match the
# field's own declared type (e.g. an auto-populated integer primary key
# with an ORM-level ``default=''`` from a ``blank=True`` fallback); such
# mismatched defaults are invalid OpenAPI and must be dropped rather than
# emitted.
_DEFAULT_PYTHON_TYPES = {
    'string': (str,),
    'integer': (int,),
    'number': (int, float),
    'boolean': (bool,),
    'array': (list, tuple),
    'object': (dict,),
}


def _has_default(field_info):
    """Whether the field declares a default at all.

    Tastypie spells "no default" two ways -- the ``NOT_PROVIDED`` class
    itself, and an instance of it -- so both are checked here rather than
    inline, where the reading was a double negative.
    """
    default = field_info.get('default')
    return not (default is NOT_PROVIDED or isinstance(default, NOT_PROVIDED))


def _publishable_default(default, schema_type):
    """Whether ``default`` may be published as the default of ``schema_type``.

    A ``bool`` is an ``int`` in Python, so ``True`` would otherwise be
    published as the default of an integer field. The rule is stated as "a
    bool is only ever a boolean's default" rather than by comparing against
    a particular entry of ``_DEFAULT_PYTHON_TYPES``, which made it depend on
    how that table happened to spell its tuples.

    An unrecognised ``schema_type`` publishes the default unchecked: the
    type map is the authority on what is checkable, not on what is valid.
    """
    expected = _DEFAULT_PYTHON_TYPES.get(schema_type)
    if expected is None:
        return True
    if isinstance(default, bool) and schema_type != 'boolean':
        return False
    return isinstance(default, expected)


def field_to_schema(field_info, *, override=None):
    """Convert one ``build_schema()`` field entry to a schema object.

    ``override`` is merged last, so a hand-written ``Docs.field_schemas``
    entry -- or a ``DEFAULT_FIELD_SCHEMAS`` fragment, for a field tastypie
    generates -- wins over anything derived from the field.
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
    if _has_default(field_info) and not callable(default):
        if _publishable_default(default, schema.get('type')):
            schema['default'] = default

    if override:
        schema.update(override)
    return schema
