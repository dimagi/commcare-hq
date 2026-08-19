"""Shared machinery for validating instances against generated OpenAPI
schemas.

Used by both ``test_examples_validate.py`` (checked-in examples against
their own schema) and ``test_contract.py`` (real API responses against
the response schema), so the ``$ref``-resolution setup lives here once.
"""

from openapi_schema_validator import OAS30Validator


def validator_for(document, schema):
    """An ``OAS30Validator`` for ``schema``, able to resolve ``$ref``s
    against the rest of ``document``.

    OAS30Validator (not a plain jsonschema Draft7Validator) because
    OpenAPI 3.0 schemas use the ``nullable`` keyword, which plain JSON
    Schema doesn't understand -- a bare Draft7Validator would reject
    every legitimately-null value (e.g. PaginationMeta's "next") as a
    false positive, unrelated to whether the instance is actually wrong.

    Built by evolving a validator rooted at ``document`` rather than by
    constructing one on ``schema`` directly: ``schema`` is a fragment of
    ``document``, so a ``"$ref": "#/components/schemas/Foo"`` inside it
    has to resolve against the whole document. ``evolve()`` swaps the
    schema while keeping the resolver anchored at ``document``, which a
    validator constructed on ``schema`` alone cannot do -- its fragments
    would resolve against ``schema`` itself and raise ``Unresolvable``.
    """
    return OAS30Validator(document).evolve(schema=schema)


def assert_matches_schema(document, schema, instance, *, context=''):
    """Assert ``instance`` validates against ``schema`` within ``document``."""
    validator = validator_for(document, schema)
    errors = list(validator.iter_errors(instance))
    assert not errors, (
        f'{context}: does not match its schema: '
        f'{"; ".join(e.message for e in errors)}'
    )


def response_record_schema_and_instances(schema, instance):
    """The object-level schema and the concrete record(s) it describes,
    for a *response* schema/instance pair.

    Forward validation (``assert_matches_schema``) only checks that
    whatever is present is well-formed -- it can't catch a schema
    describing fields the API never returns, or a response that includes
    fields the schema never mentions, because extra and missing
    properties are both legal JSON Schema unless ``required`` or
    ``additionalProperties: false`` say otherwise. Comparing the
    *declared field names* against the *actual field names* of a record
    catches both.

    A list response wraps records as ``{'meta': ..., 'objects': [...]}``;
    a detail or create response is the record itself. Returns
    ``(None, None)`` for a schema with no ``properties`` at all -- not a
    record-shaped response this convention applies to.
    """
    properties = schema.get('properties')
    if properties is None:
        return None, None
    objects_property = properties.get('objects', {})
    if 'items' in objects_property:
        item_schema = objects_property['items']
        return item_schema.get('properties', {}), instance.get('objects', [])
    return properties, [instance]


def declared_response_fields(record_properties):
    """Property names that a response record schema promises to include.

    Returns every declared property except those marked ``writeOnly``.
    A ``writeOnly`` property appears only in a request body, so a
    response is never expected to include it.
    """
    return {
        name
        for name, prop in record_properties.items()
        if not prop.get('writeOnly')
    }
