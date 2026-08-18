"""Shared machinery for validating instances against generated OpenAPI
schemas.

Used by both ``test_examples_validate.py`` (checked-in examples against
their own schema) and ``test_contract.py`` (real API responses against
the response schema), so the ``$ref``-resolution setup lives here once.
"""

import jsonschema
from openapi_schema_validator import OAS30Validator


def validator_for(document, schema):
    """An ``OAS30Validator`` for ``schema``, able to resolve ``$ref``s
    against the rest of ``document``.

    OAS30Validator (not a plain jsonschema Draft7Validator) because
    OpenAPI 3.0 schemas use the ``nullable`` keyword, which plain JSON
    Schema doesn't understand -- a bare Draft7Validator would reject
    every legitimately-null value (e.g. PaginationMeta's "next") as a
    false positive, unrelated to whether the instance is actually wrong.
    """
    resolver = jsonschema.RefResolver.from_schema(document)
    return OAS30Validator(schema, resolver=resolver)


def assert_matches_schema(document, schema, instance, *, context=''):
    """Assert ``instance`` validates against ``schema`` within ``document``."""
    validator = validator_for(document, schema)
    errors = list(validator.iter_errors(instance))
    assert not errors, (
        f'{context}: does not match its schema: '
        f'{"; ".join(e.message for e in errors)}'
    )
