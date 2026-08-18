"""Every shipped example must validate against the schema it's attached to.

Without this, a schema and its example can be self-consistently wrong --
both silently agree with each other while disagreeing with what the API
actually does -- and a plain "are the example's keys a subset of the
schema's properties" check will not catch it (a subset check does not
verify ``required``, ``oneOf``/``anyOf`` branch membership, ``enum``
values, and so on).
"""

import pytest

from corehq.apps.api.openapi.builder import build_all
from corehq.apps.api.openapi.tests.oas_validation import (
    declared_response_fields,
    response_record_schema_and_instances,
    validator_for,
)

# Fields that only appear in a response when the caller explicitly opts
# in via a ``<field>__full=true`` query parameter (Tastypie's
# ``UseIfRequested`` wrapper -- see corehq/apps/api/fields.py). A plain
# example, which doesn't set that parameter, legitimately omits them;
# that's not the schema or the example being wrong about the API, it's
# the API being conditional. Keyed by path, not by doc_slug -- the same
# path is documented once under its own spec (e.g. ``case-v1``) and
# again under ``bundle``, and the exemption needs to apply both times.
CONDITIONALLY_ABSENT_FIELDS = {
    '/a/{domain}/api/case/v1/': {
        'xforms_by_name',
        'xforms_by_xmlns',
        'child_cases',
        'parent_cases',
    },
    '/a/{domain}/api/form/v1/': {'cases'},
}


def _iter_examples(documents):
    """Yield (spec, path, method, kind, schema, example) for every example
    attached to a request body or a response in the generated documents.
    """
    for spec, document in documents.items():
        for path, item in document.get('paths', {}).items():
            for method, operation in item.items():
                if method == 'parameters':
                    continue
                request_body = operation.get('requestBody')
                if request_body:
                    body = request_body.get('content', {}).get(
                        'application/json', {}
                    )
                    if 'example' in body and 'schema' in body:
                        yield (
                            spec,
                            path,
                            method,
                            'requestBody',
                            body['schema'],
                            body['example'],
                            document,
                        )
                for status, response in operation.get('responses', {}).items():
                    body = response.get('content', {}).get(
                        'application/json', {}
                    )
                    if 'example' in body and 'schema' in body:
                        yield (
                            spec,
                            path,
                            method,
                            f'response {status}',
                            body['schema'],
                            body['example'],
                            document,
                        )


def _examples():
    documents = build_all()
    return list(_iter_examples(documents))


def _response_examples():
    # Request examples are excluded: a request legitimately sends only a
    # subset of the writable fields (e.g. a PATCH updating one field), so
    # "every declared field must be present" does not apply to them --
    # only to responses, which the API always populates in full.
    return [example for example in _examples() if example[3] != 'requestBody']


@pytest.mark.parametrize(
    'spec, path, method, kind, schema, example, document',
    _examples(),
    ids=[
        f'{spec}:{path}:{method}:{kind}'
        for spec, path, method, kind, *_ in _examples()
    ],
)
def test_example_validates_against_its_own_schema(
    spec,
    path,
    method,
    kind,
    schema,
    example,
    document,
):
    validator = validator_for(document, schema)
    errors = list(validator.iter_errors(example))
    assert not errors, (
        f'{spec} {method.upper()} {path} ({kind}): example does not '
        f'match its own schema: {"; ".join(e.message for e in errors)}'
    )


@pytest.mark.parametrize(
    'spec, path, method, kind, schema, example, document',
    _response_examples(),
    ids=[
        f'{spec}:{path}:{method}:{kind}'
        for spec, path, method, kind, *_ in _response_examples()
    ],
)
def test_response_example_has_every_declared_field_and_no_others(
    spec,
    path,
    method,
    kind,
    schema,
    example,
    document,
):
    """A response example must agree with its schema about field names,
    in both directions.

    Forward validation (``test_example_validates_against_its_own_schema``)
    only checks that whatever is present is well-formed. It cannot catch
    a schema describing a field the API never returns, or a response
    that includes a field the schema never mentions -- both of those are
    legal JSON Schema, since neither ``required`` nor
    ``additionalProperties: false`` is declared. This is exactly the
    class of bug that let a stale, RST-sourced example ship a phantom
    "type" field for user-v1 while omitting "eulas" and "resource_uri",
    silently agreeing with a schema that was itself correct.
    """
    record_schema, instances = response_record_schema_and_instances(
        schema, example
    )
    assert record_schema is not None, (
        f'{spec} {method.upper()} {path} ({kind}): response schema has '
        'no properties to compare the example against'
    )
    should_appear = declared_response_fields(
        record_schema
    ) - CONDITIONALLY_ABSENT_FIELDS.get(path, set())
    declared = set(record_schema)
    for instance in instances:
        actual = set(instance)
        missing = should_appear - actual
        extra = actual - declared
        assert not missing and not extra, (
            f'{spec} {method.upper()} {path} ({kind}): example '
            'disagrees with its schema about which fields exist -- '
            f'missing from example: {sorted(missing)}; '
            f'present in example but not in schema: {sorted(extra)}'
        )


def test_at_least_one_example_is_covered():
    # A sanity check that this test file's parametrization isn't
    # silently empty (e.g. because build_all() stopped producing
    # examples) -- a test with zero cases "passes" without checking
    # anything.
    assert len(_examples()) >= 5
