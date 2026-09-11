"""Reading the response fields out of a generated OpenAPI document.

Every function here takes an already-loaded spec: the dict returned by
``artifacts.read_spec()``, or one just built by ``builder.build_all()``.
None of them take a slug or a file path, so they can be tested by passing
a dict literal, with no need to write a file to a temporary directory.

Finding the response fields in a spec takes some work, so it is done once,
in ``_record_property_items()``, rather than in each function. A response
schema may be a ``$ref``, it may branch through ``anyOf``/``oneOf``/
``allOf``, and a list response wraps its records in an envelope whose own
fields (``meta``, ``next``, etc.) are not record fields.
"""

_REF_PREFIX = '#/components/schemas/'


def _resolve(schema, spec, seen):
    """Follow a chain of local ``$ref``s to the schema they name.

    Returns ``(schema, seen)`` -- the refs followed come back with it, because
    a caller that recurses into ``anyOf`` branches must know what has already
    been followed or a self-referential document recurses forever.

    Returns an empty schema for a ref already in ``seen``, and for a remote
    or malformed ref (which this generator does not produce).
    """
    while True:
        ref = schema.get('$ref')
        if ref is None:
            return schema, seen
        if ref in seen or not ref.startswith(_REF_PREFIX):
            return {}, seen
        seen = seen | {ref}
        schema = (
            spec.get('components', {})
            .get('schemas', {})
            .get(ref[len(_REF_PREFIX):], {})
        )


# Property names under which a list-style response nests its array of
# records. Tastypie list responses use ``objects``; the case API's list
# and bulk-fetch responses use ``cases``. When a response's top-level
# properties include one of these, wrapping an array, the coverage count
# is about the *records'* fields, not the envelope's own bookkeeping
# fields (``meta``/``matching_records``/``next``).
_RECORD_ARRAY_KEYS = ('objects', 'cases')


def _record_property_items(schema, spec, seen=frozenset()):
    """Yield ``(name, property)`` pairs for one record's fields.

    Detail responses are the record itself; list responses wrap it in an
    envelope property of array values (see ``_RECORD_ARRAY_KEYS``). A
    response may also be a ``$ref``, or branch through ``anyOf``/
    ``oneOf``/``allOf`` -- ``case-v2``'s detail response does, and its
    ``cases`` array items are themselves an ``anyOf`` (a case or an
    error stub).

    Every branch is traversed, and a name may be yielded more than once,
    so the caller must treat a field as described if any occurrence
    describes it.
    """
    schema, seen = _resolve(schema, spec, seen)
    for key in ('anyOf', 'oneOf', 'allOf'):
        if key in schema:
            for branch in schema[key]:
                yield from _record_property_items(branch, spec, seen)
            return
    properties = schema.get('properties', {})
    for key in _RECORD_ARRAY_KEYS:
        array = properties.get(key)
        if isinstance(array, dict) and array.get('type') == 'array':
            yield from _record_property_items(
                array.get('items', {}), spec, seen
            )
            return
    yield from properties.items()


def record_properties(spec):
    """Yield ``(path, method, status, name, property)`` for every record
    field of every success response in ``spec``."""
    for path, item in spec.get('paths', {}).items():
        for method, operation in item.items():
            if method == 'parameters':
                continue
            for status, response in operation.get('responses', {}).items():
                if not status.startswith('2'):
                    continue
                schema = (
                    response.get('content', {})
                    .get('application/json', {})
                    .get('schema')
                )
                if not schema:
                    continue
                for name, prop in _record_property_items(schema, spec):
                    if isinstance(prop, dict):
                        yield path, method, status, name, prop


def description_coverage(spec):
    """Returns the ``spec``'s response properties that carry a description
    as ``(described, total)``.

    Each property name is counted once across every success response, so
    a field documented on one endpoint is not counted again on
    another -- which is the right measure for the index page's "how
    documented is this API" badge, but means a field described on one
    endpoint and not another still counts as described. Use
    ``undescribed_fields()`` for the per-endpoint question.
    """
    described = {}
    for _, _, _, name, prop in record_properties(spec):
        described[name] = described.get(name, False) or 'description' in prop
    return (sum(described.values()), len(described))


def undescribed_fields(spec):
    """Every place ``spec`` publishes a record field with no description.

    Returns a sorted list of ``(path, method, name)``. Unlike
    ``description_coverage()``, a field is reported per operation, so one
    described on the detail response and not the list response is still
    reported -- the reference page renders each operation's schema
    separately, so that the reader sees an undescribed field either way.
    """
    return sorted(
        (path, method, name)
        for path, method, _, name, prop in record_properties(spec)
        if 'description' not in prop
    )
